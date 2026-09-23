"""
test_stations.py — Unit & Integration tests for Station Registry & Real-Time Health Status (F11)
"""

from datetime import datetime, timezone
import uuid
import pytest
from fastapi.testclient import TestClient

from storage.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    QCResult,
    QCVerdict,
    RawReading,
    Station,
    StationStatus,
)
from storage.seed import seed_database
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from main import app
from storage.base import Base
from storage.db import get_db


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database for stations tests."""
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


@pytest.fixture
def api_client(memory_db):
    """FastAPI TestClient with overridden get_db using the test in-memory SQLite session."""
    def override_get_db():
        try:
            yield memory_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_list_stations_empty_db(api_client: TestClient, memory_db):
    """Empty DB returns zero stations cleanly."""
    resp = api_client.get("/api/stations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["healthy_count"] == 0
    assert data["anomalous_count"] == 0
    assert data["stations"] == []


def test_list_stations_with_seeded_stations(api_client: TestClient, memory_db):
    """Seeded database returns all 20 stations with valid coordinate metadata."""
    seed_database(memory_db)
    resp = api_client.get("/api/stations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 20
    # Before any readings are ingested, active stations default to offline
    assert data["offline_count"] == 20
    assert len(data["stations"]) == 20

    first_st = data["stations"][0]
    assert "station_code" in first_st
    assert "latitude" in first_st
    assert "longitude" in first_st
    assert "health_status" in first_st
    assert first_st["health_status"] == "offline"


def test_station_health_aggregation_lifecycle(api_client: TestClient, memory_db):
    """
    Verifies that a station transitions properly:
    1. No readings -> offline
    2. Valid reading -> healthy
    3. Anomalous QC verdict / active alert -> anomalous
    """
    st = Station(
        id=uuid.uuid4(),
        station_code="HEALTH_TEST_01",
        name="Health Test Station",
        latitude=28.6139,
        longitude=77.2090,
        elevation_m=216.0,
        state="Delhi",
        district="New Delhi",
        status=StationStatus.active,
    )
    memory_db.add(st)
    memory_db.commit()

    # 1. Initially offline
    resp1 = api_client.get(f"/api/stations/{st.station_code}")
    assert resp1.status_code == 200
    assert resp1.json()["health_status"] == "offline"

    # 2. Add valid reading
    r1 = RawReading(
        station_id=st.id,
        timestamp=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        temperature=32.5,
        humidity=55.0,
        pressure=1010.0,
        wind_speed=3.2,
        wind_direction=180.0,
        rainfall=0.0,
        solar_radiation=600.0,
    )
    memory_db.add(r1)
    memory_db.commit()

    qc_valid = QCResult(
        reading_id=r1.id,
        station_id=st.id,
        variable="temperature",
        verdict=QCVerdict.valid,
        reason_code="VALID_READING",
        fault_type=None,
        confidence=0.95,
        details={},
    )
    memory_db.add(qc_valid)
    memory_db.commit()

    resp2 = api_client.get(f"/api/stations/{st.station_code}")
    assert resp2.status_code == 200
    detail2 = resp2.json()
    assert detail2["health_status"] == "healthy"
    assert detail2["latest_reading"]["temperature"] == 32.5
    assert detail2["active_alerts_count"] == 0

    # 3. Add anomalous reading and alert
    r2 = RawReading(
        station_id=st.id,
        timestamp=datetime(2024, 6, 1, 13, 0, 0, tzinfo=timezone.utc),
        temperature=68.0,
        humidity=20.0,
    )
    memory_db.add(r2)
    memory_db.commit()

    qc_anom = QCResult(
        reading_id=r2.id,
        station_id=st.id,
        variable="temperature",
        verdict=QCVerdict.anomalous,
        reason_code="RULE_RANGE_MAX",
        fault_type="spike",
        confidence=0.99,
        details={"value": 68.0},
    )
    memory_db.add(qc_anom)
    memory_db.commit()

    alert = Alert(
        station_id=st.id,
        qc_result_id=qc_anom.id,
        severity=AlertSeverity.critical,
        status=AlertStatus.open,
        message="Critical spike on temperature: 68.0°C exceeds sensor spec max",
    )
    memory_db.add(alert)
    memory_db.commit()

    # Check station detail
    resp3 = api_client.get(f"/api/stations/{st.station_code}")
    assert resp3.status_code == 200
    detail3 = resp3.json()
    assert detail3["health_status"] == "anomalous"
    assert detail3["active_alerts_count"] == 1
    assert detail3["latest_reading"]["temperature"] == 68.0
    assert len(detail3["active_alerts"]) == 1

    # Check station in list API
    list_resp = api_client.get("/api/stations")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["anomalous_count"] == 1
    st_item = next(item for item in list_data["stations"] if item["station_code"] == "HEALTH_TEST_01")
    assert st_item["health_status"] == "anomalous"
    assert st_item["active_alerts_count"] == 1


def test_list_stations_filter_by_state(api_client: TestClient, memory_db):
    """Filtering by Indian State returns only matching stations."""
    seed_database(memory_db)
    delhi_resp = api_client.get("/api/stations?state=Delhi")
    assert delhi_resp.status_code == 200
    delhi_data = delhi_resp.json()
    assert delhi_data["total"] > 0
    assert all(st["state"] == "Delhi" for st in delhi_data["stations"])

    rajasthan_resp = api_client.get("/api/stations?state=Rajasthan")
    assert rajasthan_resp.status_code == 200
    raj_data = rajasthan_resp.json()
    assert raj_data["total"] > 0
    assert all(st["state"] == "Rajasthan" for st in raj_data["stations"])


def test_get_station_detail_by_uuid(api_client: TestClient, memory_db):
    """Station detail can be retrieved by UUID."""
    st = Station(
        id=uuid.uuid4(),
        station_code="UUID_TEST_ST",
        name="UUID Test Station",
        latitude=19.0760,
        longitude=72.8777,
        state="Maharashtra",
        district="Mumbai",
        status=StationStatus.active,
    )
    memory_db.add(st)
    memory_db.commit()

    resp = api_client.get(f"/api/stations/{str(st.id)}")
    assert resp.status_code == 200
    assert resp.json()["station_code"] == "UUID_TEST_ST"
    assert resp.json()["state"] == "Maharashtra"


def test_get_station_detail_not_found(api_client: TestClient, memory_db):
    """Non-existent station returns HTTP 404."""
    resp = api_client.get("/api/stations/NON_EXISTENT_STATION")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_get_station_telemetry_with_qc_overlay(api_client: TestClient, memory_db):
    """Telemetry endpoint returns chronological stream with merged QC diagnostics."""
    st = Station(
        id=uuid.uuid4(),
        station_code="TELEMETRY_QC_ST",
        name="Telemetry QC Station",
        latitude=28.7,
        longitude=77.1,
        state="Delhi",
        district="North Delhi",
        sensor_specs={"temperature": {"min": -10.0, "max": 50.0}},
        status=StationStatus.active,
    )
    memory_db.add(st)
    memory_db.commit()

    # Reading 1: Normal
    r1 = RawReading(
        station_id=st.id,
        timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        temperature=32.0,
        humidity=60.0,
    )
    memory_db.add(r1)

    # Reading 2: Anomalous Spike
    r2 = RawReading(
        station_id=st.id,
        timestamp=datetime(2024, 6, 1, 11, 0, 0, tzinfo=timezone.utc),
        temperature=65.0,
        humidity=25.0,
    )
    memory_db.add(r2)
    memory_db.commit()

    # QC Result on Reading 2
    qc = QCResult(
        reading_id=r2.id,
        station_id=st.id,
        variable="temperature",
        verdict=QCVerdict.anomalous,
        reason_code="RULE_RANGE_MAX",
        fault_type="spike",
        confidence=0.99,
        details={"value": 65.0, "threshold": 50.0},
    )
    memory_db.add(qc)
    memory_db.commit()

    resp = api_client.get(f"/api/stations/{st.station_code}/telemetry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["station_code"] == "TELEMETRY_QC_ST"
    assert data["total_points"] == 2
    pts = data["telemetry"]
    assert len(pts) == 2

    # Chronological order check: r1 before r2
    assert pts[0]["temperature"] == 32.0
    assert pts[1]["temperature"] == 65.0

    # QC overlay check on r2
    assert "temperature" in pts[1]["qc_verdicts"]
    qc_info = pts[1]["qc_verdicts"]["temperature"]
    assert qc_info["verdict"] == "anomalous"
    assert qc_info["reason_code"] == "RULE_RANGE_MAX"
    assert qc_info["fault_type"] == "spike"
    assert qc_info["confidence"] == 0.99


def test_get_station_telemetry_time_filtering(api_client: TestClient, memory_db):
    """Telemetry endpoint filters by start_time, end_time, and limit."""
    st = Station(
        id=uuid.uuid4(),
        station_code="FILTER_TEST_ST",
        name="Filter Test Station",
        latitude=26.9,
        longitude=75.8,
        state="Rajasthan",
        district="Jaipur",
        status=StationStatus.active,
    )
    memory_db.add(st)
    memory_db.commit()

    # Add 5 hourly readings
    for i in range(5):
        r = RawReading(
            station_id=st.id,
            timestamp=datetime(2024, 6, 1, 10 + i, 0, 0, tzinfo=timezone.utc),
            temperature=30.0 + i,
        )
        memory_db.add(r)
    memory_db.commit()

    # Limit filter
    resp = api_client.get(f"/api/stations/{st.station_code}/telemetry?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_points"] == 2
    # Should be the latest 2 in chronological order: 13:00 and 14:00
    assert data["telemetry"][0]["temperature"] == 33.0
    assert data["telemetry"][1]["temperature"] == 34.0

    # Time window filter
    resp2 = api_client.get(
        f"/api/stations/{st.station_code}/telemetry?start_time=2024-06-01T11:00:00Z&end_time=2024-06-01T13:00:00Z"
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total_points"] == 3
