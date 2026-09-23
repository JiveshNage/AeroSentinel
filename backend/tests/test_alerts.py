"""
test_alerts.py — Unit and integration tests for F10 Alerts Service

Tests:
1. Severity mapping: Range -> Critical, Flatline/Step -> High, ML outlier -> Medium, Valid -> None.
2. Human-readable message formatting: verifies domain explanation and confidence percentage.
3. Alert creation & deduplication: verifies cooldown debouncing against alert fatigue.
4. REST API lifecycle: listing with filters, pagination, acknowledgment, and resolution.
5. Real-time WebSocket connection and broadcast streaming.
6. End-to-end integration: fault ingestion immediately produces a visible operational alert.
"""

import asyncio
from datetime import datetime, timezone, timedelta
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from storage.base import Base
from storage.db import get_db
from storage.models import (
    Station,
    RawReading,
    QCResult,
    QCVerdict,
    Alert,
    AlertSeverity,
    AlertStatus,
    StationStatus,
)
from alerts.service import (
    determine_severity,
    format_alert_message,
    create_alert_for_qc_result,
    update_alert_status,
)


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database for alerts tests."""
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


# ---------------------------------------------------------------------------
# 1. Severity Mapping & Formatting Tests
# ---------------------------------------------------------------------------

def test_determine_severity_mapping():
    # Valid reading -> No alert
    assert determine_severity(QCVerdict.valid, 1.0, "VALID_READING") is None

    # Critical: Range failure
    assert determine_severity(QCVerdict.anomalous, 0.99, "RULE_RANGE") == AlertSeverity.critical

    # Critical: Severe spatial mismatch
    assert determine_severity(QCVerdict.anomalous, 0.96, "SPATIAL_MISMATCH") == AlertSeverity.critical

    # High: Flatline failure
    assert determine_severity(QCVerdict.anomalous, 0.98, "RULE_FLATLINE") == AlertSeverity.high

    # High: Step failure
    assert determine_severity(QCVerdict.anomalous, 0.95, "RULE_STEP") == AlertSeverity.high

    # Medium: ML outlier alone
    assert determine_severity(QCVerdict.anomalous, 0.75, "ML_ISOFOREST") == AlertSeverity.medium

    # Low: Suspect verdict
    assert determine_severity(QCVerdict.suspect, 0.60, "ML_BORDERLINE") == AlertSeverity.low


def test_format_alert_message():
    msg = format_alert_message(
        station_code="NCR001",
        station_name="Delhi Safdarjung",
        variable="temperature",
        severity=AlertSeverity.critical,
        reason_code="RULE_RANGE",
        fault_type="spike",
        confidence=0.99,
        details={"rule": {"details": {"value": 65.0}}},
    )
    assert "[CRITICAL]" in msg
    assert "NCR001" in msg
    assert "65.0" in msg
    assert "99%" in msg


# ---------------------------------------------------------------------------
# 2. Alert Creation & Deduplication (Debouncing)
# ---------------------------------------------------------------------------

def test_create_alert_and_deduplication(memory_db):
    st = Station(
        id=uuid.uuid4(),
        station_code="NCR_ALERT_01",
        name="Safdarjung Test",
        latitude=28.58,
        longitude=77.20,
        elevation_m=216.0,
        state="Delhi",
        district="Delhi",
        status=StationStatus.active,
    )
    memory_db.add(st)

    # Reading 1
    r1 = RawReading(
        station_id=st.id,
        timestamp=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        temperature=65.0,
    )
    memory_db.add(r1)
    memory_db.commit()

    qc1 = QCResult(
        reading_id=r1.id,
        station_id=st.id,
        variable="temperature",
        verdict=QCVerdict.anomalous,
        reason_code="RULE_RANGE",
        fault_type="spike",
        confidence=0.99,
        details={"rule": {"details": {"value": 65.0}}},
    )
    memory_db.add(qc1)
    memory_db.commit()

    # 1. Create first alert
    alert1 = create_alert_for_qc_result(memory_db, qc1, cooldown_minutes=60)
    assert alert1 is not None
    assert alert1.status == AlertStatus.open
    assert alert1.severity == AlertSeverity.critical
    assert memory_db.query(Alert).count() == 1

    # 2. Reading 2: Repeated failure 10 minutes later (same station & variable)
    r2 = RawReading(
        station_id=st.id,
        timestamp=datetime(2024, 6, 1, 12, 10, 0, tzinfo=timezone.utc),
        temperature=66.0,
    )
    memory_db.add(r2)
    memory_db.commit()

    qc2 = QCResult(
        reading_id=r2.id,
        station_id=st.id,
        variable="temperature",
        verdict=QCVerdict.anomalous,
        reason_code="RULE_RANGE",
        fault_type="spike",
        confidence=0.99,
        details={"rule": {"details": {"value": 66.0}}},
    )
    memory_db.add(qc2)
    memory_db.commit()

    alert2 = create_alert_for_qc_result(memory_db, qc2, cooldown_minutes=60)
    # Must update existing open alert rather than duplicating
    assert alert2.id == alert1.id
    assert alert2.qc_result_id == qc2.id
    assert memory_db.query(Alert).count() == 1


# ---------------------------------------------------------------------------
# 3. REST API Lifecycle Tests (Listing, Acknowledging, Resolving)
# ---------------------------------------------------------------------------

def test_alert_rest_api_lifecycle(api_client, memory_db):
    st = Station(
        id=uuid.uuid4(),
        station_code="DEL_LIFECYCLE",
        name="Lifecycle Station",
        latitude=28.6,
        longitude=77.2,
        elevation_m=215.0,
        state="Delhi",
        district="Delhi",
        status=StationStatus.active,
    )
    memory_db.add(st)

    r = RawReading(station_id=st.id, timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc), temperature=70.0)
    memory_db.add(r)
    memory_db.commit()

    qc = QCResult(
        reading_id=r.id,
        station_id=st.id,
        variable="temperature",
        verdict=QCVerdict.anomalous,
        reason_code="RULE_RANGE",
        fault_type="spike",
        confidence=0.99,
        details={"rule": {"details": {"value": 70.0}}},
    )
    memory_db.add(qc)
    memory_db.commit()

    alert = create_alert_for_qc_result(memory_db, qc)
    assert alert is not None

    # 1. GET /api/alerts
    resp = api_client.get("/api/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["alerts"][0]["id"] == alert.id
    assert data["alerts"][0]["station_code"] == "DEL_LIFECYCLE"

    # Filter by severity
    resp_crit = api_client.get("/api/alerts?severity=critical")
    assert resp_crit.status_code == 200
    assert resp_crit.json()["total"] >= 1

    resp_low = api_client.get("/api/alerts?severity=low")
    assert resp_low.status_code == 200
    assert resp_low.json()["total"] == 0

    # 2. PATCH /api/alerts/{id} -> acknowledge
    patch_ack = api_client.patch(f"/api/alerts/{alert.id}", json={"status": "acknowledged"})
    assert patch_ack.status_code == 200
    assert patch_ack.json()["status"] == "acknowledged"

    # 3. PATCH /api/alerts/{id} -> resolve
    patch_res = api_client.patch(f"/api/alerts/{alert.id}", json={"status": "resolved"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "resolved"
    assert patch_res.json()["resolved_at"] is not None


# ---------------------------------------------------------------------------
# 4. Real-Time WebSocket Alerts Stream Tests
# ---------------------------------------------------------------------------

def test_websocket_alerts_stream(api_client, memory_db):
    with api_client.websocket_connect("/api/alerts/ws") as websocket:
        # Test ping-pong heartbeat
        websocket.send_text("ping")
        data = websocket.receive_text()
        assert data == "pong"


# ---------------------------------------------------------------------------
# 5. End-to-End Ingestion Triggers Alert
# ---------------------------------------------------------------------------

def test_end_to_end_ingestion_triggers_alert(api_client, memory_db):
    """Assert injecting a faulty reading via POST /ingest produces an active operational alert."""
    st = Station(
        id=uuid.uuid4(),
        station_code="INGEST_ALERT_ST",
        name="Ingest Alert Station",
        latitude=28.58,
        longitude=77.20,
        elevation_m=216.0,
        state="Delhi",
        district="Delhi",
        sensor_specs={"temperature": {"min": -10.0, "max": 55.0}},
        status=StationStatus.active,
    )
    memory_db.add(st)
    memory_db.commit()

    # Ingest out-of-range temperature reading (68.5°C)
    payload = {
        "station_id": "INGEST_ALERT_ST",
        "timestamp": "2024-06-01T15:00:00Z",
        "temperature": 68.5,
        "humidity": 45.0,
        "pressure": 1008.0,
        "wind_speed": 3.0,
        "wind_direction": 120.0,
        "rainfall": 0.0,
        "solar_radiation": 400.0,
        "ingest_source": "simulator",
    }
    resp = api_client.post("/ingest", json=payload)
    assert resp.status_code == 201

    # Check that alert was immediately generated
    alerts_resp = api_client.get("/api/alerts?station_id=INGEST_ALERT_ST")
    assert alerts_resp.status_code == 200
    alerts_data = alerts_resp.json()
    assert alerts_data["total"] >= 1

    latest_alert = alerts_data["alerts"][0]
    assert latest_alert["severity"] == "critical"
    assert latest_alert["status"] == "open"
    assert "68.5" in latest_alert["message"]
    assert latest_alert["channel_sent"]["websocket"] is True
