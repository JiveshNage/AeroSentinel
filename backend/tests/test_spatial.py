"""
test_spatial.py — Unit and integration tests for F7 Spatial Consistency Checker

Tests:
1. Spatial coordinate projection: 3D Earth Cartesian KDTree distance calculations and radius filtering.
2. Isolated sensor fault detection: single station anomaly vs normal neighbors (SPATIAL_MISMATCH).
3. Regional extreme weather invariance (SIH Milestone): widespread heatwave across all stations
   is verified as SPATIAL_CONSISTENT (NOT flagged as a sensor fault).
4. Edge cases: isolated stations with insufficient neighbors, missing/null sensor readings.
5. End-to-end database persistence: verifies batch queries and qc_results row storage.
"""

from datetime import datetime, timezone, timedelta
import math
import uuid
import numpy as np
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from storage.base import Base
from storage.models import Station, RawReading, QCResult, QCVerdict, StationStatus
from qc.spatial import (
    lat_lon_to_cartesian,
    StationSpatialIndex,
    check_spatial_consistency,
    evaluate_spatial_for_reading,
    run_spatial_qc_for_reading,
    get_spatial_index,
)
from qc.fault_injector import inject_plausible_extreme_weather
from ingestion.simulator import generate_synthetic_weather_stream


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database for testing spatial QC."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# 1. Coordinate Projection & KDTree Distance Tests
# ---------------------------------------------------------------------------

def test_lat_lon_to_cartesian_and_distance():
    """Assert calculated distance between Delhi Safdarjung and Delhi Ridge matches reality (~8-10 km)."""
    # Safdarjung: 28.58, 77.20
    # Ridge: 28.65, 77.18
    x1, y1, z1 = lat_lon_to_cartesian(28.58, 77.20)
    x2, y2, z2 = lat_lon_to_cartesian(28.65, 77.18)

    dist_km = math.sqrt((x1 - x2)**2 + (y1 - y2)**2 + (z1 - z2)**2)
    assert 7.0 <= dist_km <= 11.0


def test_station_spatial_index_nearest_neighbors_and_radius():
    st1 = Station(id=uuid.uuid4(), station_code="DEL001", name="Delhi Safdarjung", latitude=28.58, longitude=77.20)
    st2 = Station(id=uuid.uuid4(), station_code="DEL002", name="Delhi Ridge", latitude=28.65, longitude=77.18)
    st3 = Station(id=uuid.uuid4(), station_code="DEL003", name="Delhi Palam", latitude=28.56, longitude=77.11)
    st_mumbai = Station(id=uuid.uuid4(), station_code="BOM001", name="Mumbai Colaba", latitude=18.90, longitude=72.81)

    index = StationSpatialIndex([st1, st2, st3, st_mumbai])
    neighbors = index.find_k_nearest_neighbors(station_id=st1.id, k=5, max_distance_km=150.0)

    # Should find DEL002 and DEL003, but BOM001 (>1000km away) MUST be excluded by max_distance_km
    neighbor_ids = [nid for nid, _ in neighbors]
    assert len(neighbor_ids) == 2
    assert st2.id in neighbor_ids
    assert st3.id in neighbor_ids
    assert st_mumbai.id not in neighbor_ids


# ---------------------------------------------------------------------------
# 2. Isolated Single-Station Fault vs. Regional Weather Invariance
# ---------------------------------------------------------------------------

def test_check_spatial_consistency_isolated_station_fault():
    """
    Isolated Fault: Target station temperature spikes to 46.0°C while neighboring stations
    are all around 31.5°C.
    Must detect SPATIAL_MISMATCH with high z-score.
    """
    target_temp = 46.0
    neighbor_temps = [31.0, 31.5, 32.0, 31.8]

    is_anom, reason_code, details = check_spatial_consistency(
        target_value=target_temp,
        neighbor_values=neighbor_temps,
        min_neighbors=2,
        z_threshold=3.0,
        min_delta=3.5,
    )

    assert is_anom is True
    assert reason_code == "SPATIAL_MISMATCH"
    assert details["z_score"] >= 3.0
    assert details["spatial_delta"] >= 14.0
    assert details["neighbor_count"] == 4


def test_check_spatial_consistency_regional_extreme_weather_sih_milestone():
    """
    CRITICAL SIH MILESTONE TEST:
    A genuine heatwave event causes ALL stations across the NCR region to spike to ~45°C.
    The spatial checker must confirm agreement amongst neighbors and NOT classify it as a sensor fault!
    """
    target_temp = 45.5
    neighbor_temps = [44.8, 45.2, 46.0, 45.0]

    is_anom, reason_code, details = check_spatial_consistency(
        target_value=target_temp,
        neighbor_values=neighbor_temps,
        min_neighbors=2,
        z_threshold=3.0,
        min_delta=3.5,
    )

    # Must NOT be anomalous!
    assert is_anom is False
    assert reason_code == "SPATIAL_CONSISTENT"
    # Spatial delta is less than 0.5°C because neighbors agree
    assert details["spatial_delta"] < 1.0
    assert details["z_score"] < 1.0


# ---------------------------------------------------------------------------
# 3. Edge Cases & Robustness
# ---------------------------------------------------------------------------

def test_check_spatial_consistency_insufficient_neighbors():
    """When fewer than min_neighbors are available, gracefully return SPATIAL_INSUFFICIENT_DATA."""
    # Only 1 neighbor reading
    is_anom, code, details = check_spatial_consistency(
        target_value=32.0,
        neighbor_values=[32.5],
        min_neighbors=2,
    )
    assert is_anom is False
    assert code == "SPATIAL_INSUFFICIENT_DATA"
    assert details["reason"] == "insufficient_neighbor_readings"

    # 0 neighbor readings
    is_anom_zero, code_zero, _ = check_spatial_consistency(
        target_value=32.0,
        neighbor_values=[],
        min_neighbors=2,
    )
    assert is_anom_zero is False
    assert code_zero == "SPATIAL_INSUFFICIENT_DATA"


def test_check_spatial_consistency_null_or_nan_values():
    is_anom, code, _ = check_spatial_consistency(
        target_value=float("nan"),
        neighbor_values=[31.0, 32.0],
    )
    assert is_anom is False
    assert code == "SPATIAL_INSUFFICIENT_DATA"

    # Neighbors containing None/NaN are filtered cleanly
    is_anom2, code2, details2 = check_spatial_consistency(
        target_value=32.0,
        neighbor_values=[31.5, None, float("nan"), 32.2],
        min_neighbors=2,
    )
    assert is_anom2 is False
    assert code2 == "SPATIAL_CONSISTENT"
    assert details2["neighbor_count"] == 2


# ---------------------------------------------------------------------------
# 4. End-to-End Database Integration & Batch Query Verification
# ---------------------------------------------------------------------------

def test_spatial_end_to_end_db_integration(memory_db):
    """Seed 4 NCR stations, insert simultaneous readings with 1 fault, verify DB persistence."""
    stations = []
    for i in range(4):
        st = Station(
            id=uuid.uuid4(),
            station_code=f"NCR_SPATIAL_{i}",
            name=f"NCR Station {i}",
            latitude=28.5 + (i * 0.05),
            longitude=77.2 + (i * 0.05),
            elevation_m=215.0,
            state="Delhi",
            district="Delhi",
            status=StationStatus.active,
        )
        memory_db.add(st)
        stations.append(st)
    memory_db.commit()

    ts = datetime(2024, 6, 1, 14, 0, 0, tzinfo=timezone.utc)

    # Normal readings for stations 1, 2, 3
    for st in stations[1:]:
        r = RawReading(
            station_id=st.id,
            timestamp=ts,
            temperature=33.0,
            humidity=60.0,
        )
        memory_db.add(r)

    # Fault reading for station 0 (+15°C spike)
    fault_reading = RawReading(
        station_id=stations[0].id,
        timestamp=ts,
        temperature=48.0,
        humidity=60.0,
    )
    memory_db.add(fault_reading)
    memory_db.commit()
    memory_db.refresh(fault_reading)

    # Run spatial QC for the faulty reading
    results = run_spatial_qc_for_reading(memory_db, fault_reading.id, variables=["temperature"])
    assert len(results) == 1

    temp_res = results[0]
    assert temp_res.variable == "temperature"
    assert temp_res.verdict == QCVerdict.anomalous
    assert temp_res.reason_code == "SPATIAL_MISMATCH"
    assert temp_res.fault_type == "spatial_inconsistency"

    # Query DB to confirm persistence
    saved_rows = memory_db.query(QCResult).filter(
        QCResult.reading_id == fault_reading.id,
        QCResult.reason_code == "SPATIAL_MISMATCH",
    ).all()
    assert len(saved_rows) == 1


def test_fault_injector_plausible_extreme_weather_integration(memory_db):
    """
    Test using F5's inject_plausible_extreme_weather:
    Assert all stations undergoing the simulated regional event pass the spatial consistency check.
    """
    stations = []
    for i in range(5):
        st = Station(
            id=uuid.uuid4(),
            station_code=f"NCR_HEAT_{i}",
            name=f"Heatwave Station {i}",
            latitude=28.5 + (i * 0.04),
            longitude=77.2 + (i * 0.04),
            elevation_m=215.0,
            state="Delhi",
            district="Delhi",
            status=StationStatus.active,
        )
        memory_db.add(st)
        stations.append(st)
    memory_db.commit()

    base_time = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    clean_stream = generate_synthetic_weather_stream(stations, start_time=base_time, hours=24)

    # Inject regional heatwave (+8°C at 12:00 for 6 hours across all stations)
    event_start = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    weather_df = inject_plausible_extreme_weather(clean_stream, variable="temperature", start_time=event_start, duration_hours=6, delta=8.0)

    # Insert readings into DB for 14:00 (peak heatwave)
    peak_dt = datetime(2024, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    peak_rows = weather_df[weather_df["timestamp"] == peak_dt.isoformat()]

    reading_map = {}
    for _, row in peak_rows.iterrows():
        st_obj = next(s for s in stations if s.station_code == row["station_id"])
        r = RawReading(
            station_id=st_obj.id,
            timestamp=peak_dt,
            temperature=row["temperature"],
            humidity=row["humidity"],
        )
        memory_db.add(r)
        reading_map[st_obj.station_code] = r
    memory_db.commit()

    # Evaluate spatial check for station 0 during the regional heatwave
    st0_reading = reading_map["NCR_HEAT_0"]
    qc_res = evaluate_spatial_for_reading(memory_db, st0_reading, stations[0], variable="temperature")

    assert qc_res is not None
    assert qc_res.verdict == QCVerdict.valid
    assert qc_res.reason_code == "SPATIAL_CONSISTENT"
    # Ground truth: real extreme weather is correctly NOT flagged as an anomaly!
