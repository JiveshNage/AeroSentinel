import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from storage.base import Base
from storage.db import get_db
from storage.models import Station, RawReading
from storage.seed import seed_database


@pytest.fixture(scope="function")
def ingestion_client():
    """Create a client with an isolated, seeded SQLite in-memory database."""
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
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed registered stations
    with TestingSessionLocal() as session:
        seed_database(session)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_post_ingest_success(ingestion_client: TestClient):
    """Happy path: POST /ingest persists reading and returns 201 Created."""
    payload = {
        "station_id": "NCR001",
        "timestamp": "2024-06-01T12:00:00Z",
        "temperature": 34.2,
        "humidity": 62.5,
        "pressure": 1005.4,
        "wind_speed": 4.5,
        "wind_direction": 120.0,
        "rainfall": 0.0,
        "solar_radiation": 850.0,
        "ingest_source": "simulator",
    }
    response = ingestion_client.post("/ingest", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "ingested"
    assert data["station_code"] == "NCR001"
    assert "reading_id" in data
    assert "station_id" in data


def test_post_ingest_duplicate_rejected(ingestion_client: TestClient):
    """F3 Done-when: Duplicate posts on (station_id, timestamp) return 409 Conflict."""
    payload = {
        "station_id": "NCR002",
        "timestamp": "2024-06-01T14:00:00Z",
        "temperature": 36.0,
        "humidity": 50.0,
    }

    # First post succeeds
    r1 = ingestion_client.post("/ingest", json=payload)
    assert r1.status_code == 201

    # Second post with identical station and timestamp MUST return 409
    r2 = ingestion_client.post("/ingest", json=payload)
    assert r2.status_code == 409
    assert "Duplicate reading" in r2.json()["detail"]


def test_post_ingest_malformed_payload(ingestion_client: TestClient):
    """F3 Done-when: Malformed payloads return 422 with a clear error."""
    # Missing required timestamp
    r1 = ingestion_client.post("/ingest", json={"station_id": "NCR001", "temperature": 30.0})
    assert r1.status_code == 422

    # Missing required station_id
    r2 = ingestion_client.post("/ingest", json={"timestamp": "2024-06-01T12:00:00Z", "temperature": 30.0})
    assert r2.status_code == 422

    # Non-numeric temperature
    r3 = ingestion_client.post("/ingest", json={
        "station_id": "NCR001",
        "timestamp": "2024-06-01T12:00:00Z",
        "temperature": "extremely_hot",
    })
    assert r3.status_code == 422

    # Impossible humidity (> 100%)
    r4 = ingestion_client.post("/ingest", json={
        "station_id": "NCR001",
        "timestamp": "2024-06-01T12:00:00Z",
        "humidity": 140.0,
    })
    assert r4.status_code == 422
    assert "Humidity must be between 0% and 100%" in str(r4.json())


def test_post_ingest_spoofed_station_rejected(ingestion_client: TestClient):
    """Security check: Readings from unregistered/spoofed stations return 404."""
    payload = {
        "station_id": "UNKNOWN_SPOOFED_999",
        "timestamp": "2024-06-01T12:00:00Z",
        "temperature": 25.0,
    }
    response = ingestion_client.post("/ingest", json=payload)
    assert response.status_code == 404
    assert "not found in registry" in response.json()["detail"]


def test_post_ingest_with_uuid_station_id(ingestion_client: TestClient):
    """Payload accepting station internal UUID directly."""
    # First query stations via a seeded station code to get its UUID
    from storage.db import SessionLocal
    # We can post to NCR003 to verify resolution
    r_code = ingestion_client.post("/ingest", json={
        "station_id": "NCR003",
        "timestamp": "2024-06-01T10:00:00Z",
        "temperature": 28.0,
    })
    assert r_code.status_code == 201
    station_uuid = r_code.json()["station_id"]

    # Post new reading using the resolved UUID
    r_uuid = ingestion_client.post("/ingest", json={
        "station_id": station_uuid,
        "timestamp": "2024-06-01T11:00:00Z",
        "temperature": 29.5,
    })
    assert r_uuid.status_code == 201
    assert r_uuid.json()["station_code"] == "NCR003"


def test_post_ingest_batch(ingestion_client: TestClient):
    """Batch ingestion endpoint supports bulk ingestion with duplicate skipping."""
    batch_payload = {
        "readings": [
            {
                "station_id": "NCR004",
                "timestamp": "2024-06-01T01:00:00Z",
                "temperature": 22.0,
                "humidity": 80.0,
            },
            {
                "station_id": "NCR004",
                "timestamp": "2024-06-01T02:00:00Z",
                "temperature": 22.5,
                "humidity": 78.0,
            },
            {
                "station_id": "NCR005",
                "timestamp": "2024-06-01T01:00:00Z",
                "temperature": 23.0,
                "humidity": 79.0,
            },
        ]
    }
    response = ingestion_client.post("/ingest/batch", json=batch_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["total_received"] == 3
    assert data["ingested"] == 3
    assert data["duplicates_skipped"] == 0

    # Send batch again with 1 duplicate and 1 new reading
    partial_batch = {
        "readings": [
            {
                "station_id": "NCR004",
                "timestamp": "2024-06-01T01:00:00Z",  # Duplicate
                "temperature": 22.0,
            },
            {
                "station_id": "NCR004",
                "timestamp": "2024-06-01T03:00:00Z",  # New
                "temperature": 24.0,
            },
        ]
    }
    response2 = ingestion_client.post("/ingest/batch", json=partial_batch)
    assert response2.status_code == 201
    data2 = response2.json()
    assert data2["total_received"] == 2
    assert data2["ingested"] == 1
    assert data2["duplicates_skipped"] == 1


def test_simulator_synthetic_generation():
    """F2 check: Synthetic weather generator creates realistic chronological multi-station data."""
    from ingestion.simulator import generate_synthetic_weather_stream
    from storage.seed import seed_database
    from storage.db import SessionLocal
    from storage.models import Station

    # Create dummy stations list
    stations = [
        Station(station_code="NCR001", name="Delhi", latitude=28.58, longitude=77.20, elevation_m=216.0),
        Station(station_code="NCR002", name="Gurugram", latitude=28.45, longitude=77.02, elevation_m=217.0),
    ]
    start = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    df = generate_synthetic_weather_stream(stations, start, hours=6)

    # 2 stations * 6 hours = 12 rows
    assert len(df) == 12
    assert set(df["station_id"].unique()) == {"NCR001", "NCR002"}

    # Verify chronological ordering
    timestamps = list(df["timestamp"])
    assert timestamps == sorted(timestamps)

    # Verify physical sanity
    assert df["temperature"].between(-10.0, 55.0).all()
    assert df["humidity"].between(0.0, 100.0).all()
    assert df["pressure"].between(850.0, 1080.0).all()


def test_simulator_direct_db_replay():
    """F2 Done-when: Running simulator visibly fills raw_readings in order."""
    from ingestion.simulator import generate_synthetic_weather_stream, run_simulator
    from storage.base import Base
    from storage.models import Station, RawReading
    from storage.seed import seed_database
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSession() as session:
        seed_database(session)
        stations = session.query(Station).limit(3).all()

        start = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        df = generate_synthetic_weather_stream(stations, start, hours=4)

        # Ingest each row using the service into this session
        from ingestion.service import ingest_reading
        from ingestion.schemas import IngestReadingRequest

        for _, row in df.iterrows():
            req = IngestReadingRequest(
                station_id=row["station_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                temperature=row["temperature"],
                humidity=row["humidity"],
                pressure=row["pressure"],
                wind_speed=row["wind_speed"],
                wind_direction=row["wind_direction"],
                rainfall=row["rainfall"],
                solar_radiation=row["solar_radiation"],
            )
            ingest_reading(session, req)

        # Verify raw_readings table has 12 entries
        readings = session.query(RawReading).order_by(RawReading.timestamp.asc()).all()
        assert len(readings) == 12

        # Verify timestamps are in chronological non-decreasing order
        r_timestamps = [r.timestamp for r in readings]
        assert r_timestamps == sorted(r_timestamps)

