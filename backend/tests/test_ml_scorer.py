"""
test_ml_scorer.py — Unit and integration tests for F6 Baseline ML Anomaly Scorer (Isolation Forest)

Tests:
1. Multi-dimensional feature engineering: delta, rolling mean/std, cyclical hour features.
2. Model training and serialization/deserialization roundtrip.
3. Scoring sensitivity: clean readings pass, large spikes and abrupt steps flagged.
4. Fault-injected benchmark evaluation: computes and asserts precision/recall per fault type.
5. Model registry versioning and atomic active flag update.
6. End-to-end database persistence to qc_results table.
"""

from datetime import datetime, timezone, timedelta
import json
import math
from pathlib import Path
import uuid
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from storage.base import Base
from storage.models import Station, RawReading, QCResult, QCVerdict, ModelRegistry, StationStatus
from ingestion.simulator import generate_synthetic_weather_stream
from qc.fault_injector import generate_labeled_benchmark_dataset
from qc.ml_scorer import (
    compute_features_for_series,
    extract_single_feature_vector,
    train_isolation_forest,
    score_reading,
    evaluate_benchmark_dataset,
    register_model_bundle,
    run_ml_scoring_for_reading,
    _MODEL_CACHE,
    ModelBundle,
)


@pytest.fixture
def clean_training_data():
    """Generates 7 days (168h) of clean hourly weather data for model training."""
    st = Station(station_code="NCR_TRAIN", name="Delhi Ridge", latitude=28.65, longitude=77.18, elevation_m=220.0)
    base_time = datetime(2024, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
    return generate_synthetic_weather_stream([st], start_time=base_time, hours=168)


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database for testing model registry and QC persistence."""
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
# 1. Feature Engineering Tests
# ---------------------------------------------------------------------------

def test_compute_features_for_series():
    values = [20.0, 22.0, 25.0, 24.0, 26.0, 28.0]
    base_time = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    timestamps = [base_time + timedelta(hours=i) for i in range(len(values))]

    feats = compute_features_for_series(values, timestamps, window_size=3)

    assert "value" in feats.columns
    assert "delta_1" in feats.columns
    assert "rolling_mean_diff" in feats.columns
    assert "rolling_std" in feats.columns
    assert "hour_sin" in feats.columns
    assert "hour_cos" in feats.columns

    # First delta is 0, second is 22.0 - 20.0 = 2.0
    assert np.isclose(feats["delta_1"].iloc[1], 2.0)

    # Diurnal features within [-1, 1]
    assert (feats["hour_sin"].abs() <= 1.0).all()
    assert (feats["hour_cos"].abs() <= 1.0).all()


def test_extract_single_feature_vector_matches_expected_dimensions():
    current_val = 32.5
    prior_vals = [28.0, 29.5, 31.0]
    now = datetime(2024, 6, 1, 14, 0, 0, tzinfo=timezone.utc)

    vec = extract_single_feature_vector(current_val, prior_vals, now, window_size=3)
    assert vec.shape == (1, 6)

    # Delta: 32.5 - 31.0 = 1.5
    assert np.isclose(vec[0][1], 1.5)


# ---------------------------------------------------------------------------
# 2. Training & Serialization Roundtrip Tests
# ---------------------------------------------------------------------------

def test_model_training_and_serialization(clean_training_data, tmp_path):
    bundle = train_isolation_forest(
        train_df=clean_training_data,
        variable="temperature",
        station_code="NCR_TRAIN",
        contamination=0.03,
        version="v1.0.0",
    )

    assert bundle.variable == "temperature"
    assert bundle.version == "v1.0.0"
    assert len(bundle.feature_names) == 6
    assert isinstance(bundle.threshold, float)

    # Save artifact
    model_path = tmp_path / "test_model.joblib"
    saved_path = bundle.save(model_path)
    assert saved_path.exists()

    # Load artifact
    loaded_bundle = ModelBundle.load(saved_path)
    assert loaded_bundle.version == bundle.version
    assert loaded_bundle.threshold == bundle.threshold
    assert len(loaded_bundle.feature_names) == len(bundle.feature_names)


# ---------------------------------------------------------------------------
# 3. Anomaly Scoring Sensitivity Tests
# ---------------------------------------------------------------------------

def test_score_reading_sensitivity(clean_training_data):
    bundle = train_isolation_forest(clean_training_data, variable="temperature", contamination=0.03)

    # Use continuous realistic observations from stream
    normal_idx = 24
    normal_val = clean_training_data["temperature"].iloc[normal_idx]
    prior_vals = clean_training_data["temperature"].iloc[normal_idx - 5 : normal_idx].tolist()
    ts_normal = clean_training_data["timestamp"].iloc[normal_idx]

    is_anom, anom_score, conf, details = score_reading(
        bundle, current_value=normal_val, prior_values=prior_vals, timestamp=ts_normal
    )

    assert is_anom is False
    assert anom_score < 0.50
    assert "raw_decision_score" in details

    # Severe abnormal spike (+18°C above actual)
    is_spike, spike_score, spike_conf, spike_details = score_reading(
        bundle, current_value=normal_val + 18.0, prior_values=prior_vals, timestamp=ts_normal
    )

    assert is_spike is True
    assert spike_score > 0.50
    assert spike_conf >= 0.50

    # NaN / None handling
    is_nan_anom, _, _, nan_details = score_reading(bundle, current_value=float("nan"), prior_values=prior_vals, timestamp=ts_normal)
    assert is_nan_anom is False
    assert nan_details["reason"] == "missing_or_nan"


# ---------------------------------------------------------------------------
# 4. Fault-Injected Benchmark Evaluation Tests
# ---------------------------------------------------------------------------

def test_evaluate_benchmark_dataset_metrics(clean_training_data, tmp_path):
    """
    Assert model flags injected anomalies on the F5 labeled benchmark dataset
    and produces per-fault-type precision/recall metrics.
    """
    # 1. Train model on clean baseline
    bundle = train_isolation_forest(clean_training_data, variable="temperature", contamination=0.04)

    # 2. Generate multi-station synthetic stream and inject faults
    stations = [
        Station(station_code=f"NCR00{i}", name=f"NCR Station {i}", latitude=28.5 + (i * 0.05), longitude=77.2, elevation_m=210.0)
        for i in range(1, 6)
    ]
    base_time = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    clean_test_df = generate_synthetic_weather_stream(stations, start_time=base_time, hours=48)
    benchmark_df = generate_labeled_benchmark_dataset(clean_test_df, seed=42)

    report_path = tmp_path / "model_eval_report.json"
    report = evaluate_benchmark_dataset(
        bundle=bundle,
        benchmark_df=benchmark_df,
        variable="temperature",
        output_report_path=report_path,
    )

    assert report_path.exists()
    assert "overall" in report
    assert "per_fault_type" in report

    # Overall metrics exist and are within [0, 1]
    overall = report["overall"]
    assert 0.0 <= overall["precision"] <= 1.0
    assert 0.0 <= overall["recall"] <= 1.0
    assert 0.0 <= overall["f1"] <= 1.0

    # Per fault type evaluations
    per_fault = report["per_fault_type"]
    assert "spike" in per_fault
    # Spikes should have very high recall with Isolation Forest on delta features
    assert per_fault["spike"]["recall"] >= 0.80


# ---------------------------------------------------------------------------
# 5. Model Registry & DB Integration Tests
# ---------------------------------------------------------------------------

def test_model_registry_atomic_activation(memory_db, clean_training_data):
    bundle_v1 = train_isolation_forest(clean_training_data, variable="temperature", version="v1.0.0")
    reg_v1 = register_model_bundle(memory_db, bundle_v1, metrics={"f1": 0.85}, artifact_path="/tmp/v1.joblib")
    assert reg_v1.is_active is True

    # Register v2: should atomically deactivate v1
    bundle_v2 = train_isolation_forest(clean_training_data, variable="temperature", version="v2.0.0")
    reg_v2 = register_model_bundle(memory_db, bundle_v2, metrics={"f1": 0.91}, artifact_path="/tmp/v2.joblib")

    # Re-query v1
    memory_db.refresh(reg_v1)
    assert reg_v1.is_active is False
    assert reg_v2.is_active is True


def test_run_ml_scoring_for_reading_db_persistence(memory_db, clean_training_data):
    # 1. Train and cache model bundle
    bundle = train_isolation_forest(clean_training_data, variable="temperature", version="v1.0.0")
    _MODEL_CACHE["temperature"] = bundle

    # 2. Seed station and reading
    station = Station(
        id=uuid.uuid4(),
        station_code="NCR_ML_TEST",
        name="ML Test Station",
        latitude=28.5,
        longitude=77.2,
        elevation_m=215.0,
        state="Delhi",
        district="South Delhi",
        sensor_specs={},
        status=StationStatus.active,
    )
    memory_db.add(station)
    memory_db.commit()

    # Prior normal readings
    base_ts = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        r = RawReading(
            station_id=station.id,
            timestamp=base_ts + timedelta(hours=i),
            temperature=30.0 + (i * 0.5),
            humidity=55.0,
        )
        memory_db.add(r)
    memory_db.commit()

    # Target reading with large spike
    target_reading = RawReading(
        station_id=station.id,
        timestamp=base_ts + timedelta(hours=5),
        temperature=49.0,  # +16.5°C jump
        humidity=55.0,
    )
    memory_db.add(target_reading)
    memory_db.commit()
    memory_db.refresh(target_reading)

    # Run ML scoring
    results = run_ml_scoring_for_reading(memory_db, target_reading.id)
    assert len(results) > 0

    temp_res = next(r for r in results if r.variable == "temperature")
    assert temp_res.reason_code == "ML_ISOFOREST"
    assert temp_res.verdict == QCVerdict.anomalous
    assert temp_res.reading_id == target_reading.id
    assert temp_res.ml_model_version == "v1.0.0"

    # Verify rows in DB
    db_rows = memory_db.query(QCResult).filter(
        QCResult.reading_id == target_reading.id,
        QCResult.reason_code == "ML_ISOFOREST",
    ).all()
    assert len(db_rows) == 1
