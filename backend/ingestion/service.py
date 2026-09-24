import uuid
from typing import List, Optional, Tuple, Dict
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from storage.models import Station, RawReading
from ingestion.schemas import IngestReadingRequest, BatchIngestRequest, IngestResponse, BatchIngestResponse


def resolve_station(db: Session, identifier: str) -> Optional[Station]:
    """Resolve station by UUID or IMD station_code."""
    # Check by station_code first
    station = db.query(Station).filter(Station.station_code == identifier.strip()).first()
    if station:
        return station

    # Check if identifier is valid UUID
    try:
        val_uuid = uuid.UUID(identifier.strip())
        return db.query(Station).filter(Station.id == val_uuid).first()
    except ValueError:
        return None


def ingest_reading(db: Session, request: IngestReadingRequest) -> RawReading:
    """Validate, deduplicate, and persist a single raw sensor reading."""
    station = resolve_station(db, request.station_id)
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station '{request.station_id}' not found in registry. Spoofed or unknown station rejected.",
        )

    # Check for existing duplicate reading (idempotency check)
    existing = (
        db.query(RawReading)
        .filter(
            RawReading.station_id == station.id,
            RawReading.timestamp == request.timestamp,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Duplicate reading: station '{station.station_code}' already has a reading at "
                f"{request.timestamp.isoformat()} (reading_id={existing.id})."
            ),
        )

    reading = RawReading(
        station_id=station.id,
        timestamp=request.timestamp,
        temperature=request.temperature,
        humidity=request.humidity,
        pressure=request.pressure,
        wind_speed=request.wind_speed,
        wind_direction=request.wind_direction,
        rainfall=request.rainfall,
        solar_radiation=request.solar_radiation,
        ingest_source=request.ingest_source,
    )

    try:
        db.add(reading)
        db.commit()
        db.refresh(reading)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Concurrent duplicate reading detected for station '{station.station_code}' at {request.timestamp.isoformat()}.",
        )

    # Multi-tier QC pipeline execution (F8 classifier merge layer)
    try:
        from qc.classifier import run_full_qc_pipeline_for_reading
        run_full_qc_pipeline_for_reading(db, reading.id)
    except Exception:
        pass

    return reading


def ingest_batch(db: Session, batch: BatchIngestRequest) -> BatchIngestResponse:
    """Ingest a batch of readings, skipping duplicates and persisting new readings."""
    if not batch.readings:
        return BatchIngestResponse(
            status="completed",
            total_received=0,
            ingested=0,
            duplicates_skipped=0,
            reading_ids=[],
        )

    # Cache stations lookup for efficiency
    all_stations = db.query(Station).all()
    stations_by_code: Dict[str, Station] = {s.station_code: s for s in all_stations}
    stations_by_id: Dict[str, Station] = {str(s.id): s for s in all_stations}

    new_readings: List[RawReading] = []
    duplicates_skipped = 0

    for item in batch.readings:
        identifier = item.station_id.strip()
        station = stations_by_code.get(identifier) or stations_by_id.get(identifier)
        if not station:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station '{item.station_id}' in batch not found in registry.",
            )

        # Check existing in DB
        existing = (
            db.query(RawReading)
            .filter(
                RawReading.station_id == station.id,
                RawReading.timestamp == item.timestamp,
            )
            .first()
        )
        if existing:
            duplicates_skipped += 1
            continue

        reading = RawReading(
            station_id=station.id,
            timestamp=item.timestamp,
            temperature=item.temperature,
            humidity=item.humidity,
            pressure=item.pressure,
            wind_speed=item.wind_speed,
            wind_direction=item.wind_direction,
            rainfall=item.rainfall,
            solar_radiation=item.solar_radiation,
            ingest_source=item.ingest_source,
        )
        new_readings.append(reading)

    if new_readings:
        try:
            db.add_all(new_readings)
            db.commit()
            for r in new_readings:
                db.refresh(r)
                try:
                    from qc.classifier import run_full_qc_pipeline_for_reading
                    run_full_qc_pipeline_for_reading(db, r.id)
                except Exception:
                    pass
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Batch ingestion failed due to duplicate entry conflict.",
            )

    return BatchIngestResponse(
        status="completed",
        total_received=len(batch.readings),
        ingested=len(new_readings),
        duplicates_skipped=duplicates_skipped,
        reading_ids=[r.id for r in new_readings],
    )


def process_file_upload(
    db: Session,
    file_bytes: bytes,
    filename: str,
    default_station_code: Optional[str] = None,
):
    """
    Parse uploaded CSV or JSON file containing AWS weather observations,
    validate against station registry, ingest records, and run the real-time QC engine.
    """
    import io
    import json
    import csv
    from datetime import datetime, timezone
    from storage.models import QCResult, QCVerdict
    from ingestion.schemas import FileUploadResponse, FileRowPreview

    raw_text = file_bytes.decode("utf-8", errors="replace")
    rows = []

    # Detect JSON format
    if filename.lower().endswith(".json") or raw_text.strip().startswith("["):
        try:
            parsed_json = json.loads(raw_text)
            if isinstance(parsed_json, list):
                rows = parsed_json
            elif isinstance(parsed_json, dict) and "readings" in parsed_json:
                rows = parsed_json["readings"]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON file format: {str(e)}",
            )
    else:
        # Parse CSV
        try:
            reader = csv.DictReader(io.StringIO(raw_text))
            for r in reader:
                rows.append(r)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid CSV structure: {str(e)}",
            )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file contains no data rows or could not be parsed.",
        )

    # Station cache lookup
    all_stations = db.query(Station).all()
    stations_by_code = {s.station_code.upper(): s for s in all_stations}
    stations_by_id = {str(s.id): s for s in all_stations}
    default_station = stations_by_code.get(default_station_code.upper()) if default_station_code else None

    def get_val(row_dict, *keys):
        for k in keys:
            if k in row_dict and row_dict[k] not in (None, "", "null", "NaN", "nan"):
                return row_dict[k]
        return None

    def to_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def parse_time(val):
        if not val:
            return datetime.now(timezone.utc)
        val_str = str(val).strip()
        # Try ISO parsing
        try:
            dt = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
        # Common meteorological date formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y/%m/%d %H:%M"):
            try:
                dt = datetime.strptime(val_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
        return datetime.now(timezone.utc)

    ingested_count = 0
    duplicates_skipped = 0
    anomalies_detected = 0
    stations_affected_set = set()
    preview_items: List[FileRowPreview] = []

    for row in rows:
        # Standardize keys to lowercase
        norm_row = {str(k).strip().lower(): v for k, v in row.items()}

        st_id_val = get_val(norm_row, "station_code", "station_id", "station", "st_id", "stationcode")
        st_obj = None
        if st_id_val:
            st_clean = str(st_id_val).strip().upper()
            st_obj = stations_by_code.get(st_clean) or stations_by_id.get(str(st_id_val).strip())
        if not st_obj:
            st_obj = default_station or (all_stations[0] if all_stations else None)

        if not st_obj:
            continue

        stations_affected_set.add(st_obj.station_code)

        time_val = get_val(norm_row, "timestamp", "time", "datetime", "date", "recorded_at")
        dt = parse_time(time_val)

        temp = to_float(get_val(norm_row, "temperature", "temp", "temp_c", "air_temp"))
        humidity = to_float(get_val(norm_row, "humidity", "rhum", "rh", "rel_humidity"))
        if humidity is not None and (humidity < 0.0 or humidity > 100.0):
            humidity = max(0.0, min(100.0, humidity))

        pressure = to_float(get_val(norm_row, "pressure", "pres", "barometer", "baro", "slp"))
        wind_speed = to_float(get_val(norm_row, "wind_speed", "wspd", "wind", "speed"))
        wind_direction = to_float(get_val(norm_row, "wind_direction", "wdir", "direction"))
        rainfall = to_float(get_val(norm_row, "rainfall", "rain", "prcp", "precipitation"))
        solar_radiation = to_float(get_val(norm_row, "solar_radiation", "srad", "solar", "radiation"))

        # Check duplicate
        existing = (
            db.query(RawReading)
            .filter(RawReading.station_id == st_obj.id, RawReading.timestamp == dt)
            .first()
        )
        if existing:
            duplicates_skipped += 1
            if len(preview_items) < 15:
                preview_items.append(
                    FileRowPreview(
                        station_code=st_obj.station_code,
                        timestamp=dt.isoformat(),
                        temperature=temp,
                        humidity=humidity,
                        pressure=pressure,
                        wind_speed=wind_speed,
                        rainfall=rainfall,
                        qc_verdict="duplicate_skipped",
                        fault_type="Already Ingested",
                    )
                )
            continue

        reading = RawReading(
            station_id=st_obj.id,
            timestamp=dt,
            temperature=temp,
            humidity=humidity,
            pressure=pressure,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            rainfall=rainfall,
            solar_radiation=solar_radiation,
            ingest_source=f"upload:{filename}",
        )
        db.add(reading)
        db.commit()
        db.refresh(reading)
        ingested_count += 1

        # Run QC Engine on reading
        qc_verdict_str = "valid"
        fault_type_str = None
        try:
            from qc.classifier import run_full_qc_pipeline_for_reading
            run_full_qc_pipeline_for_reading(db, reading.id)

            # Query resulting QC verdict
            qc_rows = db.query(QCResult).filter(QCResult.reading_id == reading.id).all()
            for q in qc_rows:
                if q.verdict == QCVerdict.anomalous:
                    qc_verdict_str = "anomalous"
                    fault_type_str = q.fault_type or q.reason_code
                    anomalies_detected += 1
                    break
                elif q.verdict == QCVerdict.suspect and qc_verdict_str != "anomalous":
                    qc_verdict_str = "suspect"
                    fault_type_str = q.fault_type or q.reason_code
        except Exception:
            pass

        if len(preview_items) < 15:
            preview_items.append(
                FileRowPreview(
                    station_code=st_obj.station_code,
                    timestamp=dt.isoformat(),
                    temperature=temp,
                    humidity=humidity,
                    pressure=pressure,
                    wind_speed=wind_speed,
                    rainfall=rainfall,
                    qc_verdict=qc_verdict_str,
                    fault_type=fault_type_str,
                )
            )

    return FileUploadResponse(
        status="success",
        filename=filename,
        total_rows=len(rows),
        ingested_count=ingested_count,
        duplicates_skipped=duplicates_skipped,
        anomalies_detected=anomalies_detected,
        stations_affected=sorted(list(stations_affected_set)),
        preview=preview_items,
        message=f"Successfully processed {len(rows)} rows: {ingested_count} ingested, {duplicates_skipped} duplicates skipped, {anomalies_detected} anomalies detected.",
    )

