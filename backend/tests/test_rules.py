"""
test_rules.py — Unit and integration tests for F4 Rule-Based QC Layer

Covers:
1. Range Check: limits, violations, boundaries, NaN/None handling.
2. Step Check: linear differences, circular angular differences (wind direction wrap around 360°), missing prior values.
3. Persistence / Flatline Check: frozen readings detection, length thresholds, floating point tolerances.
4. Meteorological Exceptions: dry-weather zero rainfall exemption, nighttime zero solar radiation exemption.
5. Sensor Specs Ground Truth: dynamic reading from station.sensor_specs rather than hardcoded constants.
6. DB Integration: run_qc_rules_for_reading writes rows to qc_results with foreign keys and metadata.
"""

from datetime import datetime, timezone, timedelta
import math
import uuid
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from storage.base import Base
from storage.models import Station, RawReading, QCResult, QCVerdict, StationStatus
from qc.rules import (
    check_range,
    check_step,
    check_persistence,
    evaluate_reading_rules,
    run_qc_rules_for_reading,
)


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database for testing QC rule persistence."""
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
# 1. Range Check Tests
# ---------------------------------------------------------------------------

def test_check_range_valid_within_bounds():
    is_valid, code, details = check_range(28.5, min_val=-10.0, max_val=55.0)
    assert is_valid is True
    assert code is None
    assert details is None


def test_check_range_exact_boundaries():
    # Min boundary
    is_valid, _, _ = check_range(-10.0, min_val=-10.0, max_val=55.0)
    assert is_valid is True
    # Max boundary
    is_valid, _, _ = check_range(55.0, min_val=-10.0, max_val=55.0)
    assert is_valid is True


def test_check_range_exceeds_max():
    is_valid, code, details = check_range(65.0, min_val=-10.0, max_val=55.0)
    assert is_valid is False
    assert code == "RULE_RANGE_FAIL"
    assert details["violation"] == "above_max"
    assert details["value"] == 65.0


def test_check_range_below_min():
    is_valid, code, details = check_range(-18.5, min_val=-10.0, max_val=55.0)
    assert is_valid is False
    assert code == "RULE_RANGE_FAIL"
    assert details["violation"] == "below_min"
    assert details["value"] == -18.5


def test_check_range_none_value():
    """None sensor values are not range violations (dropout/null handled separately)."""
    is_valid, code, details = check_range(None, min_val=-10.0, max_val=55.0)
    assert is_valid is True
    assert code is None


def test_check_range_nan_and_inf():
    is_valid_nan, code_nan, _ = check_range(float("nan"), min_val=-10.0, max_val=55.0)
    assert is_valid_nan is False
    assert code_nan == "RULE_RANGE_FAIL"

    is_valid_inf, code_inf, _ = check_range(float("inf"), min_val=-10.0, max_val=55.0)
    assert is_valid_inf is False
    assert code_inf == "RULE_RANGE_FAIL"


# ---------------------------------------------------------------------------
# 2. Step Check Tests
# ---------------------------------------------------------------------------

def test_check_step_normal_progression():
    is_valid, code, details = check_step(current_value=32.0, previous_value=30.5, max_step=8.0)
    assert is_valid is True
    assert code is None


def test_check_step_implausible_jump():
    """Temperature jumping 15°C in one interval must fail step check."""
    is_valid, code, details = check_step(current_value=45.0, previous_value=30.0, max_step=8.0)
    assert is_valid is False
    assert code == "RULE_STEP_FAIL"
    assert details["delta"] == 15.0
    assert details["max_step"] == 8.0


def test_check_step_missing_previous_reading():
    """First observation for a station has no previous value and must not fail."""
    is_valid, code, details = check_step(current_value=32.0, previous_value=None, max_step=8.0)
    assert is_valid is True
    assert code is None


def test_check_step_circular_wind_direction_wrap():
    """
    Wind direction moving 355° -> 5° is only a 10° angular step across North.
    With max_step=180°, it must PASS circular check.
    """
    is_valid, code, details = check_step(current_value=5.0, previous_value=355.0, max_step=90.0, is_circular=True)
    assert is_valid is True
    assert code is None

    # Reverse direction: 5° -> 355°
    is_valid_rev, _, _ = check_step(current_value=355.0, previous_value=5.0, max_step=90.0, is_circular=True)
    assert is_valid_rev is True


def test_check_step_circular_wind_direction_excessive_step():
    """Wind direction jumping from 10° to 210° (200° angular difference) exceeds 90° max_step."""
    is_valid, code, details = check_step(current_value=210.0, previous_value=10.0, max_step=90.0, is_circular=True)
    assert is_valid is False
    assert code == "RULE_STEP_FAIL"
    assert details["delta"] == 160.0  # min(200, 160) = 160°
    assert details["is_circular"] is True


# ---------------------------------------------------------------------------
# 3. Persistence / Flatline Tests
# ---------------------------------------------------------------------------

def test_check_persistence_frozen_temperature():
    """12 identical consecutive values must trigger persistence failure."""
    frozen_series = [29.4] * 12
    is_valid, code, details = check_persistence(frozen_series, max_identical=12, variable="temperature")
    assert is_valid is False
    assert code == "RULE_PERSISTENCE_FAIL"
    assert details["identical_value"] == 29.4
    assert details["consecutive_count"] == 12


def test_check_persistence_natural_variation():
    series = [28.0, 28.2, 28.5, 28.9, 29.3, 29.7]
    is_valid, code, details = check_persistence(series, max_identical=6, variable="temperature")
    assert is_valid is True
    assert code is None


def test_check_persistence_insufficient_history():
    """Fewer samples than max_identical must not fail persistence check."""
    series = [30.0, 30.0, 30.0]
    is_valid, code, details = check_persistence(series, max_identical=6, variable="temperature")
    assert is_valid is True


def test_check_persistence_with_none_or_nan():
    """If NaN or None is in the window, cannot assert identical freeze."""
    series = [30.0, 30.0, None, 30.0, 30.0, 30.0]
    is_valid, code, details = check_persistence(series, max_identical=6, variable="temperature")
    assert is_valid is True


# ---------------------------------------------------------------------------
# 4. Domain Meteorological Exception Tests
# ---------------------------------------------------------------------------

def test_check_persistence_dry_weather_rainfall_zeros_exempt():
    """12 consecutive 0.0 mm rainfall readings in dry weather is normal weather, NOT a fault."""
    dry_series = [0.0] * 12
    is_valid, code, details = check_persistence(dry_series, max_identical=6, variable="rainfall")
    assert is_valid is True
    assert code is None


def test_check_persistence_nonzero_rainfall_flatline_fails():
    """6 consecutive non-zero rainfall readings (e.g. 15.2 mm) is an implausible gauge flatline."""
    stuck_rain = [15.2] * 6
    is_valid, code, details = check_persistence(stuck_rain, max_identical=6, variable="rainfall")
    assert is_valid is False
    assert code == "RULE_PERSISTENCE_FAIL"


def test_check_persistence_nighttime_solar_radiation_zeros_exempt():
    """Consecutive 0.0 W/m² solar radiation at night is physically valid, NOT a fault."""
    night_solar = [0.0] * 8
    is_valid, code, details = check_persistence(night_solar, max_identical=6, variable="solar_radiation")
    assert is_valid is True
    assert code is None


def test_check_persistence_daytime_solar_radiation_flatline_fails():
    """Consecutive non-zero solar radiation readings (e.g. 500 W/m²) denotes a stuck pyranometer."""
    stuck_solar = [500.0] * 6
    is_valid, code, details = check_persistence(stuck_solar, max_identical=6, variable="solar_radiation")
    assert is_valid is False
    assert code == "RULE_PERSISTENCE_FAIL"


# ---------------------------------------------------------------------------
# 5. Station Sensor Specs Ground Truth Tests
# ---------------------------------------------------------------------------

def test_evaluate_reading_rules_uses_station_sensor_specs():
    """
    Assert thresholds are loaded from station.sensor_specs (not hardcoded).
    Station A has custom temperature max = 38.0°C.
    A reading of 42.0°C must fail on Station A, even though default max is 55.0°C.
    """
    station = Station(
        id=uuid.uuid4(),
        station_code="HIGH_ALT_01",
        name="High Altitude Station",
        latitude=32.2,
        longitude=77.1,
        elevation_m=2050.0,
        state="Himachal Pradesh",
        district="Kullu",
        sensor_specs={
            "temperature": {"min": -25.0, "max": 38.0, "step_max": 6.0, "persistence_max": 6},
        },
    )

    reading = RawReading(
        id=101,
        station_id=station.id,
        timestamp=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        temperature=42.0,  # Violates station max of 38.0°C
        humidity=50.0,
    )

    qc_results = evaluate_reading_rules(reading=reading, station=station, recent_readings=[])
    temp_result = next(r for r in qc_results if r.variable == "temperature")

    assert temp_result.verdict == QCVerdict.anomalous
    assert temp_result.reason_code == "RULE_RANGE_FAIL"
    assert temp_result.details["max"] == 38.0
    assert temp_result.details["value"] == 42.0


# ---------------------------------------------------------------------------
# 6. Database Integration Tests
# ---------------------------------------------------------------------------

def test_run_qc_rules_for_reading_db_persistence(memory_db):
    """Assert run_qc_rules_for_reading evaluates and persists QCResult records in DB."""
    # 1. Seed station
    station = Station(
        id=uuid.uuid4(),
        station_code="NCR_TEST",
        name="Delhi Test Station",
        latitude=28.6,
        longitude=77.2,
        elevation_m=215.0,
        state="Delhi",
        district="New Delhi",
        sensor_specs={
            "temperature": {"min": -10.0, "max": 55.0, "step_max": 8.0, "persistence_max": 4},
            "humidity": {"min": 0.0, "max": 100.0, "step_max": 30.0, "persistence_max": 4},
        },
        status=StationStatus.active,
    )
    memory_db.add(station)
    memory_db.commit()

    base_time = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

    # 2. Insert 3 prior readings with constant temperature (flatline precursor)
    for i in range(3):
        r = RawReading(
            station_id=station.id,
            timestamp=base_time + timedelta(hours=i),
            temperature=31.5,
            humidity=60.0 + (i * 2.0),
        )
        memory_db.add(r)
    memory_db.commit()

    # 3. Insert 4th reading with same temperature (should trigger 4-count persistence fail)
    fourth_reading = RawReading(
        station_id=station.id,
        timestamp=base_time + timedelta(hours=3),
        temperature=31.5,  # 4th identical reading
        humidity=66.0,
    )
    memory_db.add(fourth_reading)
    memory_db.commit()
    memory_db.refresh(fourth_reading)

    # 4. Run QC rules for the fourth reading
    results = run_qc_rules_for_reading(memory_db, fourth_reading.id)
    assert len(results) > 0

    # 5. Query QCResult rows from database to verify persistence
    db_results = memory_db.query(QCResult).filter(QCResult.reading_id == fourth_reading.id).all()
    assert len(db_results) == len(results)

    temp_db_res = next(r for r in db_results if r.variable == "temperature")
    assert temp_db_res.verdict == QCVerdict.anomalous
    assert temp_db_res.reason_code == "RULE_PERSISTENCE_FAIL"
    assert temp_db_res.fault_type == "flatline"
    assert temp_db_res.station_id == station.id

    hum_db_res = next(r for r in db_results if r.variable == "humidity")
    assert hum_db_res.verdict == QCVerdict.valid
    assert hum_db_res.reason_code == "VALID_READING"
