import uuid
from datetime import datetime, timezone, date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from storage.base import Base
from storage.models import (
    Station,
    StationStatus,
    RawReading,
    QCResult,
    QCVerdict,
    Alert,
    AlertSeverity,
    AlertStatus,
    Feedback,
    FeedbackLabel,
    User,
    UserRole,
    ModelRegistry,
    MaintenancePrediction,
)
from storage.seed import seed_database, DEFAULT_SENSOR_SPECS
from sqlalchemy import event


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh in-memory database for testing schemas and relationships."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_seed_populates_stations_and_user(test_db):
    """F1 Done-when check: seed script populates ~20 stations and admin user."""
    count = seed_database(test_db)
    assert count >= 15
    assert count == 20

    stations = test_db.query(Station).all()
    assert len(stations) == 20

    # Verify NCR001
    delhi = test_db.query(Station).filter(Station.station_code == "NCR001").first()
    assert delhi is not None
    assert delhi.name == "Delhi (Safdarjung)"
    assert delhi.latitude == pytest.approx(28.5822)
    assert delhi.longitude == pytest.approx(77.2066)
    assert delhi.sensor_specs["temperature"]["min"] == -10.0
    assert delhi.sensor_specs["temperature"]["max"] == 55.0
    assert delhi.status == StationStatus.active

    # Verify default user seeded
    user = test_db.query(User).filter(User.email == "operator@imd.gov.in").first()
    assert user is not None
    assert user.role == UserRole.data_quality_officer


def test_station_unique_code_constraint(test_db):
    """Adversarial check: inserting duplicate station_code raises IntegrityError."""
    st1 = Station(
        station_code="TEST01",
        name="Station One",
        latitude=28.5,
        longitude=77.2,
        state="Delhi",
        district="New Delhi",
        sensor_specs=DEFAULT_SENSOR_SPECS,
    )
    test_db.add(st1)
    test_db.commit()

    st2 = Station(
        station_code="TEST01",
        name="Station Duplicate",
        latitude=28.6,
        longitude=77.3,
        state="Delhi",
        district="New Delhi",
        sensor_specs=DEFAULT_SENSOR_SPECS,
    )
    test_db.add(st2)
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


def test_raw_reading_idempotent_unique_constraint(test_db):
    """Adversarial check: duplicate (station_id, timestamp) in raw_readings raises IntegrityError."""
    station = Station(
        station_code="TEST_IDEMP",
        name="Test Station",
        latitude=28.5,
        longitude=77.2,
        state="Delhi",
        district="New Delhi",
        sensor_specs=DEFAULT_SENSOR_SPECS,
    )
    test_db.add(station)
    test_db.commit()

    reading_time = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    r1 = RawReading(
        station_id=station.id,
        timestamp=reading_time,
        temperature=35.5,
        humidity=60.0,
    )
    test_db.add(r1)
    test_db.commit()

    # Second reading at identical timestamp for same station
    r2 = RawReading(
        station_id=station.id,
        timestamp=reading_time,
        temperature=35.5,
        humidity=60.0,
    )
    test_db.add(r2)
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


def test_null_sensor_variable_support(test_db):
    """Edge case: missing/null solar_radiation or rainfall must store cleanly without errors."""
    station = Station(
        station_code="TEST_NULLS",
        name="Test Nulls",
        latitude=28.5,
        longitude=77.2,
        state="Delhi",
        district="New Delhi",
        sensor_specs=DEFAULT_SENSOR_SPECS,
    )
    test_db.add(station)
    test_db.commit()

    r = RawReading(
        station_id=station.id,
        timestamp=datetime.now(timezone.utc),
        temperature=32.0,
        humidity=55.0,
        pressure=1008.0,
        wind_speed=4.2,
        wind_direction=180.0,
        rainfall=None,
        solar_radiation=None,  # sensor not installed
    )
    test_db.add(r)
    test_db.commit()
    assert r.id is not None
    assert r.solar_radiation is None
    assert r.rainfall is None


def test_cascade_delete_relationships(test_db):
    """Relationship integrity: deleting station cascades to raw_readings, qc_results, and alerts."""
    station = Station(
        station_code="CASCADE_TEST",
        name="Cascade Station",
        latitude=28.5,
        longitude=77.2,
        state="Delhi",
        district="New Delhi",
        sensor_specs=DEFAULT_SENSOR_SPECS,
    )
    test_db.add(station)
    test_db.commit()

    reading = RawReading(
        station_id=station.id,
        timestamp=datetime.now(timezone.utc),
        temperature=30.0,
    )
    test_db.add(reading)
    test_db.commit()

    qc = QCResult(
        reading_id=reading.id,
        station_id=station.id,
        variable="temperature",
        verdict=QCVerdict.anomalous,
        reason_code="RULE_RANGE",
        fault_type="spike",
        confidence=0.95,
        details={"min": -10.0, "max": 55.0, "value": 62.0},
    )
    test_db.add(qc)
    test_db.commit()

    alert = Alert(
        station_id=station.id,
        qc_result_id=qc.id,
        severity=AlertSeverity.high,
        status=AlertStatus.open,
        message="Temperature spike detected on CASCADE_TEST",
    )
    test_db.add(alert)
    test_db.commit()

    # Now delete station
    test_db.delete(station)
    test_db.commit()

    assert test_db.query(RawReading).filter(RawReading.station_id == station.id).count() == 0
    assert test_db.query(QCResult).filter(QCResult.station_id == station.id).count() == 0
    assert test_db.query(Alert).filter(Alert.station_id == station.id).count() == 0


def test_feedback_and_user_relationship(test_db):
    """Operator feedback correctly links to user and qc_result."""
    station = Station(
        station_code="FB_TEST",
        name="Feedback Test",
        latitude=28.5,
        longitude=77.2,
        state="Delhi",
        district="New Delhi",
        sensor_specs=DEFAULT_SENSOR_SPECS,
    )
    user = User(
        name="Test Officer",
        email="test_officer@imd.gov.in",
        role=UserRole.forecaster,
        password_hash="hash",
    )
    test_db.add_all([station, user])
    test_db.commit()

    reading = RawReading(station_id=station.id, timestamp=datetime.now(timezone.utc), temperature=25.0)
    test_db.add(reading)
    test_db.commit()

    qc = QCResult(
        reading_id=reading.id,
        station_id=station.id,
        variable="temperature",
        verdict=QCVerdict.suspect,
        reason_code="RULE_STEP",
        confidence=0.7,
        details={},
    )
    test_db.add(qc)
    test_db.commit()

    feedback = Feedback(
        qc_result_id=qc.id,
        user_id=user.id,
        label=FeedbackLabel.false_alarm,
        notes="Real sudden weather change confirmed with radar",
    )
    test_db.add(feedback)
    test_db.commit()

    assert feedback.id is not None
    assert feedback.qc_result.variable == "temperature"
    assert feedback.user.email == "test_officer@imd.gov.in"


def test_model_registry_and_maintenance_predictions(test_db):
    """Model registry and maintenance prediction schemas validate correctly."""
    station = Station(
        station_code="MR_TEST",
        name="Model Registry Test",
        latitude=28.5,
        longitude=77.2,
        state="Delhi",
        district="New Delhi",
        sensor_specs=DEFAULT_SENSOR_SPECS,
    )
    test_db.add(station)
    test_db.commit()

    model = ModelRegistry(
        model_type="isolation_forest",
        variable="temperature",
        version="v1.0.0",
        metrics={"precision": 0.92, "recall": 0.88, "f1": 0.90},
        artifact_path="models/isolation_forest_temp_v1.joblib",
        is_active=True,
    )
    test_db.add(model)

    pred = MaintenancePrediction(
        station_id=station.id,
        failure_probability_30d=0.28,
        top_factors={"flatline_frequency": 3, "drift_slope": 0.05},
    )
    test_db.add(pred)
    test_db.commit()

    assert model.id is not None
    assert model.is_active is True
    assert pred.id is not None
    assert pred.failure_probability_30d == pytest.approx(0.28)


def test_alembic_migrations_lifecycle(tmp_path):
    """F1 Done-when check: Alembic migrations run clean to head and downgrade to base."""
    from pathlib import Path
    from alembic.config import Config
    from alembic import command

    backend_dir = Path(__file__).resolve().parent.parent
    test_db_path = tmp_path / "test_migration_lifecycle.db"
    db_url = f"sqlite:///{test_db_path}"

    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Upgrade to head
    command.upgrade(alembic_cfg, "head")

    # Downgrade back to base cleanly
    command.downgrade(alembic_cfg, "base")

