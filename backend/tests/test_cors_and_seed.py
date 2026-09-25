"""
test_cors_and_seed.py — Comprehensive tests for CORS headers, OPTIONS preflight,
and station seed / initialization behaviors in production & local environments.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from storage.base import Base
from storage.db import get_db
from storage.models import Station
from storage.seed import seed_database, DEFAULT_NCR_STATIONS


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database session."""
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
def client(memory_db):
    """FastAPI TestClient with overridden DB session."""
    def override_get_db():
        try:
            yield memory_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# CORS TESTS
# ============================================================================

def test_cors_options_preflight_production_vercel(client: TestClient):
    """Production Vercel origin preflight OPTIONS request returns 200 with required headers."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "https://aero-sentinel-sandy.vercel.app",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://aero-sentinel-sandy.vercel.app"
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_cors_options_preflight_localhost(client: TestClient):
    """Local development origin (localhost:5173) preflight OPTIONS returns 200 with CORS headers."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_get_production_origin_allowed(client: TestClient):
    """GET request from production Vercel origin includes Access-Control-Allow-Origin."""
    response = client.get(
        "/api/health",
        headers={"Origin": "https://aero-sentinel-sandy.vercel.app"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://aero-sentinel-sandy.vercel.app"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_get_localhost_origin_allowed(client: TestClient):
    """GET request from local development includes Access-Control-Allow-Origin."""
    response = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_disallows_arbitrary_unauthorized_origin(client: TestClient):
    """Untrusted origins should not receive Access-Control-Allow-Origin header."""
    response = client.get(
        "/api/health",
        headers={"Origin": "https://malicious-phishing-site.example.com"},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "endpoint,method",
    [
        ("/api/health", "GET"),
        ("/api/alerts", "GET"),
        ("/api/stations", "GET"),
        ("/api/tasks", "GET"),
        ("/api/auth/login", "POST"),
        ("/api/admin/audit-logs", "GET"),
    ],
)
def test_cors_preflight_on_all_affected_endpoints(client: TestClient, endpoint: str, method: str):
    """Verify OPTIONS preflight succeeds with CORS headers on all 6 user-reported endpoints."""
    response = client.options(
        endpoint,
        headers={
            "Origin": "https://aero-sentinel-sandy.vercel.app",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert response.status_code == 200, f"Preflight failed on {endpoint}"
    assert response.headers.get("access-control-allow-origin") == "https://aero-sentinel-sandy.vercel.app"
    assert response.headers.get("access-control-allow-credentials") == "true"


# ============================================================================
# STATION SEED & INITIALIZATION TESTS
# ============================================================================

def test_seed_database_creates_ncr001_and_fleet(memory_db):
    """Verify seed_database idempotently populates NCR001 and >= 20 total stations."""
    count = seed_database(memory_db)
    assert count >= 20

    # Query station NCR001 directly
    st = memory_db.query(Station).filter(Station.station_code == "NCR001").first()
    assert st is not None, "Station NCR001 must exist after seeding"
    assert st.station_code == "NCR001"
    assert "Safdarjung" in st.name
    assert st.state == "Delhi"
    assert st.latitude == pytest.approx(28.5822, rel=1e-3)
    assert st.longitude == pytest.approx(77.2066, rel=1e-3)
    assert st.sensor_specs is not None
    assert "temperature" in st.sensor_specs


def test_station_endpoints_work_with_seeded_ncr001(client: TestClient, memory_db):
    """GET /api/stations/NCR001 and simulate-tick return 200 when database is seeded."""
    seed_database(memory_db)

    # 1. GET /api/stations
    res_list = client.get("/api/stations")
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["total"] >= 20
    assert any(s["station_code"] == "NCR001" for s in data["stations"])

    # 2. GET /api/stations/NCR001
    res_detail = client.get("/api/stations/NCR001")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["station_code"] == "NCR001"

    # 3. GET /api/stations/NCR001/telemetry
    res_telem = client.get("/api/stations/NCR001/telemetry?limit=30")
    assert res_telem.status_code == 200

    # 4. POST /api/stations/NCR001/simulate-tick
    res_tick = client.post("/api/stations/NCR001/simulate-tick", json={"force_anomaly": False})
    assert res_tick.status_code == 200
    tick_data = res_tick.json()
    assert "id" in tick_data
    assert "temperature" in tick_data
    assert "qc_verdicts" in tick_data


def test_default_ncr_stations_integrity():
    """Verify DEFAULT_NCR_STATIONS contains valid schema specifications for all NCR stations."""
    assert len(DEFAULT_NCR_STATIONS) == 15
    codes = [s["station_code"] for s in DEFAULT_NCR_STATIONS]
    assert "NCR001" in codes
    assert "NCR002" in codes
    assert "NCR015" in codes
    for st in DEFAULT_NCR_STATIONS:
        assert "station_code" in st
        assert "name" in st
        assert "latitude" in st
        assert "longitude" in st
        assert "state" in st
        assert "district" in st
