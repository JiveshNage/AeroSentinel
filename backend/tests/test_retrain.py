"""
test_retrain.py — Unit and integration tests for F14 Model Retraining Job (Phase 4: Learning Loop)

Tests:
1. Feedback pool statistics endpoint: correctly tallies confirmed_fault, false_alarm, unsure counts.
2. Feedback sample extraction: parses raw readings, history, and feature vectors.
3. Retraining execution & atomic registry flip: new model version activated, old deactivated.
4. Measurable before/after false alarm reduction: a false positive reading flagged by baseline
   is scored as valid under the retrained model.
5. Model version listing and rollback/activation endpoint.
"""

from datetime import datetime, timezone, timedelta
import math
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
    Feedback,
    FeedbackLabel,
    ModelRegistry,
    StationStatus,
)
from qc.ml_scorer import (
    train_isolation_forest,
    register_model_bundle,
    score_reading,
    get_active_model_bundle,
    _MODEL_CACHE,
)
from retrain.service import (
    extract_feedback_samples,
    get_feedback_pool_stats,
    execute_retrain_job,
    activate_model_version,
)
import pandas as pd


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database for retrain tests."""
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
    """FastAPI TestClient with overridden get_db using test SQLite session."""
    def override_get_db():
        try:
            yield memory_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def setup_station_and_baseline(memory_db):
    """Seed test station, historical baseline readings, and initial v1.0.0 model."""
    st = Station(
        id=uuid.uuid4(),
        station_code="RETRAIN_ST01",
        name="Retrain Test Station",
        latitude=28.58,
        longitude=77.20,
        elevation_m=216.0,
        state="Delhi",
        district="Delhi",
        status=StationStatus.active,
    )
    memory_db.add(st)

    # Generate 5 days of clean diurnal readings
    start_ts = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    readings = []
    clean_records = []
    for i in range(120):
        t = start_ts + timedelta(hours=1 * i)
        val = 28.0 + 8.0 * math.sin(2 * math.pi * (t.hour - 9) / 24.0)
        r = RawReading(
            station_id=st.id,
            timestamp=t,
            temperature=val,
            humidity=55.0,
            pressure=1012.0,
            wind_speed=2.5,
        )
        memory_db.add(r)
        readings.append(r)
        clean_records.append({"timestamp": t, "temperature": val})

    memory_db.commit()

    # Train and register v1.0.0 baseline model
    train_df = pd.DataFrame(clean_records)
    v1_bundle = train_isolation_forest(
        train_df=train_df,
        variable="temperature",
        station_code=st.station_code,
        version="v1.0.0",
        contamination=0.03,
        random_state=42,
    )
    reg_v1 = register_model_bundle(
        db=memory_db,
        bundle=v1_bundle,
        metrics={"f1": 0.85},
        artifact_path=f"/tmp/test_temperature_v1.0.0.joblib",
    )
    _MODEL_CACHE["temperature"] = v1_bundle

    return st, readings, v1_bundle, reg_v1


# ---------------------------------------------------------------------------
# 1. Feedback Stats and Extraction Tests
# ---------------------------------------------------------------------------

def test_feedback_pool_stats_and_sample_extraction(memory_db, setup_station_and_baseline):
    st, readings, _, _ = setup_station_and_baseline

    # Create reading with QC Result and False Alarm feedback
    r_fa = readings[-2]
    qc_fa = QCResult(
        reading_id=r_fa.id,
        station_id=st.id,
        variable="temperature",
        verdict=QCVerdict.anomalous,
        reason_code="ML_ISOFOREST",
        confidence=0.75,
    )
    memory_db.add(qc_fa)
    memory_db.commit()

    fb_fa = Feedback(
        qc_result_id=qc_fa.id,
        label=FeedbackLabel.false_alarm,
        notes="Microclimate heatwave",
        created_at=datetime.now(timezone.utc),
    )
    memory_db.add(fb_fa)

    # Create reading with QC Result and Confirmed Fault feedback
    r_cf = readings[-1]
    qc_cf = QCResult(
        reading_id=r_cf.id,
        station_id=st.id,
        variable="temperature",
        verdict=QCVerdict.anomalous,
        reason_code="RULE_RANGE",
        confidence=0.99,
    )
    memory_db.add(qc_cf)
    memory_db.commit()

    fb_cf = Feedback(
        qc_result_id=qc_cf.id,
        label=FeedbackLabel.confirmed_fault,
        notes="True hardware short-circuit",
        created_at=datetime.now(timezone.utc),
    )
    memory_db.add(fb_cf)
    memory_db.commit()

    # 1. Test get_feedback_pool_stats
    stats = get_feedback_pool_stats(memory_db, variable="temperature")
    assert stats.total_feedback_count == 2
    assert stats.false_alarms_count == 1
    assert stats.confirmed_faults_count == 1
    assert stats.can_retrain is True
    assert stats.active_model_version == "v1.0.0"

    # 2. Test extract_feedback_samples
    fa_samples, cf_samples = extract_feedback_samples(memory_db, variable="temperature")
    assert len(fa_samples) == 1
    assert len(cf_samples) == 1
    assert fa_samples[0]["reading_id"] == r_fa.id
    assert len(fa_samples[0]["feature_vector"]) == 6  # 6D feature vector


# ---------------------------------------------------------------------------
# 2. Retraining Execution & Atomic Registry Flip Tests
# ---------------------------------------------------------------------------

def test_execute_retrain_job_atomic_flip(memory_db, setup_station_and_baseline):
    st, readings, _, reg_v1 = setup_station_and_baseline

    # Verify v1.0.0 is currently active
    assert reg_v1.is_active is True

    # Add false alarm feedback
    r = readings[-1]
    qc = QCResult(
        reading_id=r.id,
        station_id=st.id,
        variable="temperature",
        verdict=QCVerdict.anomalous,
        reason_code="ML_ISOFOREST",
        confidence=0.70,
    )
    memory_db.add(qc)
    memory_db.commit()

    fb = Feedback(
        qc_result_id=qc.id,
        label=FeedbackLabel.false_alarm,
        notes="Heat island effect confirmed valid",
        created_at=datetime.now(timezone.utc),
    )
    memory_db.add(fb)
    memory_db.commit()

    # Trigger retraining
    retrain_resp = execute_retrain_job(
        db=memory_db,
        variable="temperature",
        new_version="v1.1.0",
        target_false_alarm_reduction=1.0,
    )

    assert retrain_resp.new_version == "v1.1.0"
    assert retrain_resp.previous_version == "v1.0.0"
    assert retrain_resp.metrics["false_alarms_count"] == 1

    # Verify database model_registry atomic transition
    memory_db.refresh(reg_v1)
    assert reg_v1.is_active is False  # Old model deactivated!

    reg_new = memory_db.query(ModelRegistry).filter(ModelRegistry.version == "v1.1.0").first()
    assert reg_new is not None
    assert reg_new.is_active is True  # New model activated!

    # Verify memory cache was updated
    active_bundle = get_active_model_bundle("temperature")
    assert active_bundle.version == "v1.1.0"


# ---------------------------------------------------------------------------
# 3. Measurable False Alarm Reduction (Phase 4 Exit Criterion)
# ---------------------------------------------------------------------------

def test_false_alarm_reduction_before_and_after(memory_db, setup_station_and_baseline):
    """
    CRITICAL PHASE 4 TEST:
    Assert a reading flagged as anomalous by the baseline model is scored as
    VALID (non-anomalous) under the retrained model after false-alarm feedback.
    """
    st, readings, v1_bundle, _ = setup_station_and_baseline

    # Create a legitimate but abrupt microclimate warm spell (36.0°C when baseline expected ~33°C)
    test_ts = datetime(2024, 6, 6, 14, 0, 0, tzinfo=timezone.utc)
    warm_val = 37.0
    prior_vals = [getattr(r, "temperature") for r in readings[-10:]]

    # 1. BEFORE: Baseline v1.0.0 scores this reading as ANOMALOUS (False Positive)
    # We calibrate v1 threshold so this reading is anomalous
    v1_bundle.threshold = 0.05
    is_anom_before, score_before, _, _ = score_reading(
        bundle=v1_bundle,
        current_value=warm_val,
        prior_values=prior_vals,
        timestamp=test_ts,
    )
    assert is_anom_before is True, "Reading must initially trigger an anomaly on baseline model"

    # 2. Operator reviews alert and flags it as a FALSE ALARM (e.g. natural desert breeze)
    r_test = RawReading(station_id=st.id, timestamp=test_ts, temperature=warm_val)
    memory_db.add(r_test)
    memory_db.commit()

    qc_test = QCResult(
        reading_id=r_test.id,
        station_id=st.id,
        variable="temperature",
        verdict=QCVerdict.anomalous,
        reason_code="ML_ISOFOREST",
        confidence=0.72,
    )
    memory_db.add(qc_test)
    memory_db.commit()

    fb = Feedback(
        qc_result_id=qc_test.id,
        label=FeedbackLabel.false_alarm,
        notes="Validated natural desert breeze heat wave",
        created_at=datetime.now(timezone.utc),
    )
    memory_db.add(fb)
    memory_db.commit()

    # 3. Retrain model incorporating this false-alarm ground truth
    retrain_res = execute_retrain_job(
        db=memory_db,
        variable="temperature",
        new_version="v1.1.0-retrained",
        target_false_alarm_reduction=1.0,
    )

    assert retrain_res.metrics["false_alarm_reduction_pct"] == 100.0

    # 4. AFTER: Score the EXACT same reading under the newly activated model
    retrained_bundle = get_active_model_bundle("temperature")
    assert retrained_bundle.version == "v1.1.0-retrained"

    is_anom_after, score_after, _, _ = score_reading(
        bundle=retrained_bundle,
        current_value=warm_val,
        prior_values=prior_vals,
        timestamp=test_ts,
    )

    # MUST now be evaluated as VALID (no longer anomalous)
    assert is_anom_after is False, "Retrained model must no longer flag the operator-cleared false alarm!"


# ---------------------------------------------------------------------------
# 4. REST API Integration & Rollback Tests
# ---------------------------------------------------------------------------

def test_retrain_rest_api_lifecycle_and_rollback(api_client, memory_db, setup_station_and_baseline):
    st, readings, _, reg_v1 = setup_station_and_baseline

    # 1. GET /api/retrain/stats
    resp_stats = api_client.get("/api/retrain/stats?variable=temperature")
    assert resp_stats.status_code == 200
    assert "total_feedback_count" in resp_stats.json()

    # 2. Trigger Retrain via POST /api/retrain/trigger
    payload = {
        "variable": "temperature",
        "new_version": "v2.0.0",
        "target_false_alarm_reduction": 1.0,
    }
    resp_retrain = api_client.post("/api/retrain/trigger", json=payload)
    assert resp_retrain.status_code == 200
    data = resp_retrain.json()
    assert data["new_version"] == "v2.0.0"
    v2_id = data["model_registry_id"]

    # 3. GET /api/retrain/models
    resp_models = api_client.get("/api/retrain/models?variable=temperature")
    assert resp_models.status_code == 200
    models_list = resp_models.json()["models"]
    assert len(models_list) >= 2

    # Check that v2.0.0 is active and v1.0.0 is inactive
    v2_entry = next(m for m in models_list if m["version"] == "v2.0.0")
    v1_entry = next(m for m in models_list if m["version"] == "v1.0.0")
    assert v2_entry["is_active"] is True
    assert v1_entry["is_active"] is False

    # 4. Rollback: POST /api/retrain/models/{id}/activate -> reactivate v1.0.0
    resp_activate = api_client.post(f"/api/retrain/models/{reg_v1.id}/activate")
    assert resp_activate.status_code == 200
    assert resp_activate.json()["is_active"] is True

    # Verify v2.0.0 is now inactive
    resp_models_after = api_client.get("/api/retrain/models?variable=temperature")
    models_list_after = resp_models_after.json()["models"]
    v2_after = next(m for m in models_list_after if m["version"] == "v2.0.0")
    v1_after = next(m for m in models_list_after if m["version"] == "v1.0.0")
    assert v1_after["is_active"] is True
    assert v2_after["is_active"] is False
