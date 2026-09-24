"""
stations.py — Station Registry & Real-Time Health Status API (F11)
"""

from datetime import datetime, timezone, timedelta
import enum
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from storage.db import get_db
from storage.models import Alert, AlertStatus, QCResult, QCVerdict, RawReading, Station, StationStatus


router = APIRouter(prefix="/stations", tags=["stations"])


class StationHealthStatus(str, enum.Enum):
    healthy = "healthy"
    suspect = "suspect"
    anomalous = "anomalous"
    offline = "offline"


class LatestReadingSchema(BaseModel):
    timestamp: datetime
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    rainfall: Optional[float] = None
    solar_radiation: Optional[float] = None


class StationSummaryResponse(BaseModel):
    id: uuid.UUID
    station_code: str
    name: str
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    state: str
    district: str
    status: StationStatus
    health_status: StationHealthStatus
    latest_reading: Optional[LatestReadingSchema] = None
    latest_verdict: Optional[QCVerdict] = None
    active_alerts_count: int = 0
    latest_fault_type: Optional[str] = None
    sensor_specs: Dict[str, Any] = Field(default_factory=dict)


class StationListResponse(BaseModel):
    total: int
    healthy_count: int
    suspect_count: int
    anomalous_count: int
    offline_count: int
    stations: List[StationSummaryResponse]


class StationDetailResponse(StationSummaryResponse):
    recent_readings: List[LatestReadingSchema] = []
    active_alerts: List[Dict[str, Any]] = []


class QCVariableVerdictSchema(BaseModel):
    verdict: QCVerdict
    reason_code: str
    fault_type: Optional[str] = None
    confidence: float
    details: Dict[str, Any] = Field(default_factory=dict)


class TelemetryPointSchema(BaseModel):
    id: int
    timestamp: datetime
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    rainfall: Optional[float] = None
    solar_radiation: Optional[float] = None
    qc_verdicts: Dict[str, QCVariableVerdictSchema] = Field(default_factory=dict)


class StationTelemetryResponse(BaseModel):
    station_id: uuid.UUID
    station_code: str
    name: str
    sensor_specs: Dict[str, Any]
    total_points: int
    telemetry: List[TelemetryPointSchema]


@router.get("", response_model=StationListResponse)
def list_stations(
    state: Optional[str] = Query(None, description="Filter by Indian State"),
    status_filter: Optional[StationStatus] = Query(None, alias="status", description="Filter by station administrative status"),
    db: Session = Depends(get_db),
):
    """
    List all weather stations with aggregated real-time health verdicts,
    latest sensor telemetry, and active alert counters.

    Uses batch aggregation queries to prevent N+1 overhead.
    """
    query = db.query(Station)
    if state:
        query = query.filter(Station.state == state)
    if status_filter:
        query = query.filter(Station.status == status_filter)

    stations = query.order_by(Station.state, Station.station_code).all()
    if not stations:
        return StationListResponse(
            total=0,
            healthy_count=0,
            suspect_count=0,
            anomalous_count=0,
            offline_count=0,
            stations=[],
        )

    station_ids = [s.id for s in stations]

    # 1. Batch fetch latest reading per station (subquery max timestamp)
    subq_reading = (
        db.query(RawReading.station_id, func.max(RawReading.timestamp).label("max_ts"))
        .filter(RawReading.station_id.in_(station_ids))
        .group_by(RawReading.station_id)
        .subquery()
    )
    latest_readings = (
        db.query(RawReading)
        .join(subq_reading, (RawReading.station_id == subq_reading.c.station_id) & (RawReading.timestamp == subq_reading.c.max_ts))
        .all()
    )
    latest_readings_map = {r.station_id: r for r in latest_readings}

    # 2. Batch fetch active alert count per station
    alert_counts = (
        db.query(Alert.station_id, func.count(Alert.id).label("cnt"))
        .filter(Alert.station_id.in_(station_ids), Alert.status != AlertStatus.resolved)
        .group_by(Alert.station_id)
        .all()
    )
    alert_counts_map = {st_id: cnt for st_id, cnt in alert_counts}

    # 3. Batch fetch latest QC verdict per station (subquery max id)
    subq_qc = (
        db.query(QCResult.station_id, func.max(QCResult.id).label("max_id"))
        .filter(QCResult.station_id.in_(station_ids))
        .group_by(QCResult.station_id)
        .subquery()
    )
    latest_qcs = (
        db.query(QCResult)
        .join(subq_qc, (QCResult.station_id == subq_qc.c.station_id) & (QCResult.id == subq_qc.c.max_id))
        .all()
    )
    latest_qc_map = {q.station_id: q for q in latest_qcs}

    # Assemble response items
    station_summaries: List[StationSummaryResponse] = []
    healthy_cnt = 0
    suspect_cnt = 0
    anomalous_cnt = 0
    offline_cnt = 0

    for st in stations:
        reading = latest_readings_map.get(st.id)
        qc = latest_qc_map.get(st.id)
        active_alerts = alert_counts_map.get(st.id, 0)

        # Health determination logic
        if st.status != StationStatus.active or reading is None:
            health = StationHealthStatus.offline
            offline_cnt += 1
        elif active_alerts > 0 or (qc and qc.verdict == QCVerdict.anomalous):
            health = StationHealthStatus.anomalous
            anomalous_cnt += 1
        elif qc and qc.verdict == QCVerdict.suspect:
            health = StationHealthStatus.suspect
            suspect_cnt += 1
        else:
            health = StationHealthStatus.healthy
            healthy_cnt += 1

        reading_schema = None
        if reading:
            reading_schema = LatestReadingSchema(
                timestamp=reading.timestamp,
                temperature=reading.temperature,
                humidity=reading.humidity,
                pressure=reading.pressure,
                wind_speed=reading.wind_speed,
                wind_direction=reading.wind_direction,
                rainfall=reading.rainfall,
                solar_radiation=reading.solar_radiation,
            )

        summary = StationSummaryResponse(
            id=st.id,
            station_code=st.station_code,
            name=st.name,
            latitude=st.latitude,
            longitude=st.longitude,
            elevation_m=st.elevation_m,
            state=st.state,
            district=st.district,
            status=st.status,
            health_status=health,
            latest_reading=reading_schema,
            latest_verdict=qc.verdict if qc else None,
            active_alerts_count=active_alerts,
            latest_fault_type=qc.fault_type if qc else None,
            sensor_specs=st.sensor_specs or {},
        )
        station_summaries.append(summary)

    return StationListResponse(
        total=len(station_summaries),
        healthy_count=healthy_cnt,
        suspect_count=suspect_cnt,
        anomalous_count=anomalous_cnt,
        offline_count=offline_cnt,
        stations=station_summaries,
    )


@router.get("/{station_id}", response_model=StationDetailResponse)
def get_station_detail(
    station_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve single station details with recent telemetry readings and active alerts.
    Station ID can be a UUID or station_code (e.g. 'NCR001').
    """
    query = db.query(Station)
    try:
        val_uuid = uuid.UUID(station_id)
        st = query.filter(Station.id == val_uuid).first()
    except ValueError:
        st = query.filter(Station.station_code == station_id).first()

    if not st:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station '{station_id}' not found.",
        )

    # Fetch last 50 readings
    recent_readings_rows = (
        db.query(RawReading)
        .filter(RawReading.station_id == st.id)
        .order_by(RawReading.timestamp.desc())
        .limit(50)
        .all()
    )

    recent_readings = [
        LatestReadingSchema(
            timestamp=r.timestamp,
            temperature=r.temperature,
            humidity=r.humidity,
            pressure=r.pressure,
            wind_speed=r.wind_speed,
            wind_direction=r.wind_direction,
            rainfall=r.rainfall,
            solar_radiation=r.solar_radiation,
        )
        for r in recent_readings_rows
    ]

    latest_reading = recent_readings[0] if recent_readings else None

    # Fetch active alerts
    alerts_rows = (
        db.query(Alert)
        .filter(Alert.station_id == st.id, Alert.status != AlertStatus.resolved)
        .order_by(Alert.created_at.desc())
        .all()
    )
    active_alerts = [
        {
            "id": a.id,
            "severity": a.severity.value,
            "status": a.status.value,
            "message": a.message,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts_rows
    ]

    # Latest QC verdict
    latest_qc = (
        db.query(QCResult)
        .filter(QCResult.station_id == st.id)
        .order_by(QCResult.id.desc())
        .first()
    )

    if st.status != StationStatus.active or latest_reading is None:
        health = StationHealthStatus.offline
    elif len(active_alerts) > 0 or (latest_qc and latest_qc.verdict == QCVerdict.anomalous):
        health = StationHealthStatus.anomalous
    elif latest_qc and latest_qc.verdict == QCVerdict.suspect:
        health = StationHealthStatus.suspect
    else:
        health = StationHealthStatus.healthy

    return StationDetailResponse(
        id=st.id,
        station_code=st.station_code,
        name=st.name,
        latitude=st.latitude,
        longitude=st.longitude,
        elevation_m=st.elevation_m,
        state=st.state,
        district=st.district,
        status=st.status,
        health_status=health,
        latest_reading=latest_reading,
        latest_verdict=latest_qc.verdict if latest_qc else None,
        active_alerts_count=len(active_alerts),
        latest_fault_type=latest_qc.fault_type if latest_qc else None,
        sensor_specs=st.sensor_specs or {},
        recent_readings=recent_readings,
        active_alerts=active_alerts,
    )


@router.get("/{station_id}/telemetry", response_model=StationTelemetryResponse)
def get_station_telemetry(
    station_id: str,
    start_time: Optional[datetime] = Query(None, description="Filter readings starting at UTC ISO timestamp"),
    end_time: Optional[datetime] = Query(None, description="Filter readings ending at UTC ISO timestamp"),
    limit: int = Query(100, ge=1, le=500, description="Maximum readings to return (default 100, max 500)"),
    db: Session = Depends(get_db),
):
    """
    Retrieve chronological telemetry time-series for a station with merged
    per-variable QC verdicts, reason codes, and anomaly confidence.
    """
    query = db.query(Station)
    try:
        val_uuid = uuid.UUID(station_id)
        st = query.filter(Station.id == val_uuid).first()
    except ValueError:
        st = query.filter(Station.station_code == station_id).first()

    if not st:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station '{station_id}' not found.",
        )

    # 1. Fetch raw readings for this station
    r_query = db.query(RawReading).filter(RawReading.station_id == st.id)
    if start_time:
        r_query = r_query.filter(RawReading.timestamp >= start_time)
    if end_time:
        r_query = r_query.filter(RawReading.timestamp <= end_time)

    readings = r_query.order_by(RawReading.timestamp.desc()).limit(limit).all()
    # Reverse so readings are in ascending chronological order for charts
    readings.reverse()

    if not readings:
        return StationTelemetryResponse(
            station_id=st.id,
            station_code=st.station_code,
            name=st.name,
            sensor_specs=st.sensor_specs or {},
            total_points=0,
            telemetry=[],
        )

    reading_ids = [r.id for r in readings]

    # 2. Single batch fetch for all QCResults associated with these readings
    qc_rows = db.query(QCResult).filter(QCResult.reading_id.in_(reading_ids)).all()
    qc_by_reading: Dict[int, Dict[str, QCVariableVerdictSchema]] = {}
    for qc in qc_rows:
        if qc.reading_id not in qc_by_reading:
            qc_by_reading[qc.reading_id] = {}
        qc_by_reading[qc.reading_id][qc.variable] = QCVariableVerdictSchema(
            verdict=qc.verdict,
            reason_code=qc.reason_code,
            fault_type=qc.fault_type,
            confidence=qc.confidence,
            details=qc.details or {},
        )

    # 3. Assemble response points
    telemetry_points: List[TelemetryPointSchema] = []
    for r in readings:
        point = TelemetryPointSchema(
            id=r.id,
            timestamp=r.timestamp,
            temperature=r.temperature,
            humidity=r.humidity,
            pressure=r.pressure,
            wind_speed=r.wind_speed,
            wind_direction=r.wind_direction,
            rainfall=r.rainfall,
            solar_radiation=r.solar_radiation,
            qc_verdicts=qc_by_reading.get(r.id, {}),
        )
        telemetry_points.append(point)

    return StationTelemetryResponse(
        station_id=st.id,
        station_code=st.station_code,
        name=st.name,
        sensor_specs=st.sensor_specs or {},
        total_points=len(telemetry_points),
        telemetry=telemetry_points,
    )


class SimulateTickRequest(BaseModel):
    force_anomaly: bool = False
    fault_type: Optional[str] = "spike"
    variable: Optional[str] = "temperature"


@router.post("/{station_id}/simulate-tick", response_model=TelemetryPointSchema)
def simulate_station_tick(
    station_id: str,
    payload: Optional[SimulateTickRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Generate and ingest an instantaneous real-time telemetry observation tick
    for live streaming demonstration, optionally injecting an anomaly spike.
    """
    import random
    from qc.classifier import run_full_qc_pipeline_for_reading

    query = db.query(Station)
    try:
        val_uuid = uuid.UUID(station_id)
        st = query.filter(Station.id == val_uuid).first()
    except ValueError:
        st = query.filter(Station.station_code == station_id).first()

    if not st:
        raise HTTPException(status_code=404, detail=f"Station '{station_id}' not found.")

    latest = (
        db.query(RawReading)
        .filter(RawReading.station_id == st.id)
        .order_by(RawReading.timestamp.desc())
        .first()
    )

    base_temp = latest.temperature if (latest and latest.temperature is not None) else 32.0
    base_hum = latest.humidity if (latest and latest.humidity is not None) else 62.0
    base_pres = latest.pressure if (latest and latest.pressure is not None) else 1012.0
    base_wind = latest.wind_speed if (latest and latest.wind_speed is not None) else 4.0
    base_rain = 0.0

    new_temp = round(base_temp + random.uniform(-0.3, 0.3), 2)
    new_hum = round(max(10.0, min(95.0, base_hum + random.uniform(-1.0, 1.0))), 1)
    new_pres = round(base_pres + random.uniform(-0.2, 0.2), 1)
    new_wind = round(max(0.0, base_wind + random.uniform(-0.4, 0.4)), 1)
    new_solar = round(max(0.0, random.uniform(500, 850)), 1)

    if payload and payload.force_anomaly:
        var = payload.variable or "temperature"
        f_type = payload.fault_type or "spike"
        if var == "temperature":
            new_temp = 54.8 if f_type == "out_of_bounds" else round(base_temp + 14.5, 2)
        elif var == "humidity":
            new_hum = 100.0 if f_type == "flatline" else 99.5
        elif var == "pressure":
            new_pres = 830.0 if f_type == "out_of_bounds" else round(base_pres - 25.0, 1)
        elif var == "wind_speed":
            new_wind = 48.0

    now_utc = datetime.now(timezone.utc)
    if latest and latest.timestamp:
        latest_ts = latest.timestamp.replace(tzinfo=timezone.utc) if latest.timestamp.tzinfo is None else latest.timestamp
        if latest_ts >= now_utc:
            now_utc = latest_ts + timedelta(minutes=1)

    reading = RawReading(
        station_id=st.id,
        timestamp=now_utc,
        temperature=new_temp,
        humidity=new_hum,
        pressure=new_pres,
        wind_speed=new_wind,
        wind_direction=random.randint(0, 360),
        rainfall=base_rain,
        solar_radiation=new_solar,
        ingest_source="live_stream_simulator",
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)

    try:
        run_full_qc_pipeline_for_reading(db, reading.id)
    except Exception:
        pass

    qc_rows = db.query(QCResult).filter(QCResult.reading_id == reading.id).all()
    qc_dict = {}
    for q in qc_rows:
        qc_dict[q.variable] = QCVariableVerdictSchema(
            verdict=q.verdict,
            reason_code=q.reason_code,
            fault_type=q.fault_type,
            confidence=q.confidence,
            details=q.details or {},
        )

    return TelemetryPointSchema(
        id=reading.id,
        timestamp=reading.timestamp,
        temperature=reading.temperature,
        humidity=reading.humidity,
        pressure=reading.pressure,
        wind_speed=reading.wind_speed,
        wind_direction=reading.wind_direction,
        rainfall=reading.rainfall,
        solar_radiation=reading.solar_radiation,
        qc_verdicts=qc_dict,
    )

