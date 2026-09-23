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
        return reading
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Concurrent duplicate reading detected for station '{station.station_code}' at {request.timestamp.isoformat()}.",
        )


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
