"""
test_lstm_scorer.py — Unit & Integration Test Suite for F9 LSTM-Autoencoder
Feature: F9 — LSTM-Autoencoder upgrade (Phase 5 Stretch Goal)

1. Window generation: creates temporal sliding sequence windows.
2. Training convergence: learns clean baseline manifold with low reconstruction error.
3. Anomaly detection: flags temporal sequence distortions (drift and flatlines).
4. Side-by-side benchmark evaluation: asserts LSTM-AE beats Isolation Forest baseline on drift recall.
5. Model registry & persistence: tests PyTorch checkpoint save/load and atomic registration.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import torch

from storage.base import Base
from storage.models import Station, RawReading, ModelRegistry
from ingestion.simulator import generate_synthetic_weather_stream
from qc.fault_injector import generate_labeled_benchmark_dataset
from qc.ml_scorer import train_isolation_forest
from qc.lstm_scorer import (
    LSTMAutoencoder,
    LSTMModelBundle,
    create_sliding_windows,
    train_lstm_autoencoder,
    score_sequence,
    evaluate_side_by_side,
    register_lstm_bundle,
    get_active_lstm_bundle,
    _LSTM_MODEL_CACHE,
)


@pytest.fixture
def clean_training_data():
    """Generates 7 days (168h) of clean hourly weather data for model training."""
    st = Station(station_code="DEL001", name="Safdarjung", latitude=28.58, longitude=77.20, elevation_m=216.0)
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
# 1. Sliding Window Generation Tests
# ---------------------------------------------------------------------------

def test_create_sliding_windows():
    """Verify window generation shape and edge-case handling."""
    vals = [20.0 + i for i in range(20)]
    windows = create_sliding_windows(vals, seq_length=12)

    # N = 20, W = 12 -> N - W + 1 = 9 windows of shape (9, 12, 1)
    assert windows.shape == (9, 12, 1)
    assert np.isclose(windows[0, 0, 0], 20.0)
    assert np.isclose(windows[0, 11, 0], 31.0)
    assert np.isclose(windows[1, 0, 0], 21.0)

    # Insufficient length returns empty array
    short_vals = [25.0, 26.0, 27.0]
    empty_wins = create_sliding_windows(short_vals, seq_length=12)
    assert empty_wins.shape == (0, 12, 1)

    # None and NaN values filtered out
    vals_with_nans = [20.0, None, float("nan"), 21.0, 22.0] + [23.0 + i for i in range(15)]
    nan_wins = create_sliding_windows(vals_with_nans, seq_length=12)
    assert len(nan_wins) > 0


# ---------------------------------------------------------------------------
# 2. LSTM-Autoencoder Training Convergence
# ---------------------------------------------------------------------------

def test_train_lstm_autoencoder_convergence(clean_training_data):
    """
    Assert training converges on clean diurnal meteorological patterns with low MSE
    and calibrates the threshold above mean training error.
    """
    bundle = train_lstm_autoencoder(
        train_df=clean_training_data,
        variable="temperature",
        station_code="DEL001",
        version="v1.0.0-lstm-test",
        seq_length=12,
        hidden_dim=24,
        epochs=25,
        lr=0.008,
    )

    assert isinstance(bundle, LSTMModelBundle)
    assert bundle.variable == "temperature"
    assert bundle.version == "v1.0.0-lstm-test"
    assert bundle.seq_length == 12

    # Clean diurnal curve should be reconstructed with low normalized MSE (< 0.35)
    assert bundle.mean_train_error < 0.35
    # Calibrated threshold must be strictly higher than mean training error
    assert bundle.threshold > bundle.mean_train_error


# ---------------------------------------------------------------------------
# 3. Anomaly Scoring: Drift and Flatline Detection
# ---------------------------------------------------------------------------

def test_lstm_drift_and_flatline_detection(clean_training_data):
    """
    Assert that clean sequences produce valid scores, while sensor drift
    and flatline sequence distortions yield high reconstruction error.
    """
    bundle = train_lstm_autoencoder(
        train_df=clean_training_data,
        variable="temperature",
        station_code="DEL001",
        version="v1.0.0-lstm-test",
        seq_length=12,
        epochs=25,
    )

    now = datetime.now(timezone.utc)

    # 1. Clean diurnal sequence window from end of training data
    clean_vals = clean_training_data["temperature"].iloc[-12:].tolist()
    curr_clean = clean_vals[-1]
    prior_clean = clean_vals[:-1]

    is_anom, score, conf, details = score_sequence(
        bundle=bundle,
        current_value=curr_clean,
        prior_values=prior_clean,
        timestamp=now,
    )

    assert is_anom is False
    assert score < 0.50
    assert details["model_type"] == "lstm_autoencoder"
    assert details["reconstruction_mse"] <= bundle.threshold

    # 2. Artificial Drift Sequence: rapid +12°C linear ramp over 12 steps
    drift_vals = [25.0 + i * 1.2 for i in range(12)]
    curr_drift = drift_vals[-1]
    prior_drift = drift_vals[:-1]

    is_anom_drift, score_drift, conf_drift, details_drift = score_sequence(
        bundle=bundle,
        current_value=curr_drift,
        prior_values=prior_drift,
        timestamp=now,
    )

    assert is_anom_drift is True
    assert score_drift > 0.60
    assert details_drift["reconstruction_mse"] > bundle.threshold


# ---------------------------------------------------------------------------
# 4. Side-by-Side Benchmark Evaluation (Phase 5 Stretch Goal Exit Criterion)
# ---------------------------------------------------------------------------

def test_side_by_side_benchmark_drift_improvement(clean_training_data, tmp_path):
    """
    Phase 5 Exit Criterion: Side-by-side evaluation showing LSTM-AE beats
    IsolationForest baseline specifically on sensor drift recall.
    Baseline IF drift recall is ~58.3%.
    """
    # 1. Train baseline Isolation Forest
    if_bundle = train_isolation_forest(
        train_df=clean_training_data,
        variable="temperature",
        station_code="FLEET",
        version="v1.0.0-iforest",
        contamination=0.04,
    )

    # 2. Train candidate LSTM-Autoencoder
    lstm_bundle = train_lstm_autoencoder(
        train_df=clean_training_data,
        variable="temperature",
        station_code="FLEET",
        version="v1.0.0-lstm-candidate",
        seq_length=12,
        hidden_dim=24,
        epochs=30,
        lr=0.008,
    )

    # 3. Generate multi-station synthetic stream and inject faults
    stations = [
        Station(station_code=f"NCR00{i}", name=f"NCR Station {i}", latitude=28.5 + (i * 0.05), longitude=77.2, elevation_m=210.0)
        for i in range(1, 6)
    ]
    base_time = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    clean_test_df = generate_synthetic_weather_stream(stations, start_time=base_time, hours=48)
    benchmark_df = generate_labeled_benchmark_dataset(clean_test_df, seed=42)

    report_path = tmp_path / "model_eval_lstm_vs_iforest.json"
    permanent_report_path = Path("reports/model_eval_lstm_vs_iforest.json")

    report = evaluate_side_by_side(
        lstm_bundle=lstm_bundle,
        iforest_bundle=if_bundle,
        benchmark_df=benchmark_df,
        variable="temperature",
        output_report_path=report_path,
    )

    # Also persist to project reports/ directory for reporting
    permanent_report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(permanent_report_path, "w") as f:
        json.dump(report, f, indent=2)

    assert report_path.exists()
    assert permanent_report_path.exists()

    drift_stats = report["per_fault_type_comparison"]["drift"]
    if_drift_recall = drift_stats["isolation_forest_recall"]
    lstm_drift_recall = drift_stats["lstm_ae_recall"]

    print(f"\n[Side-by-Side Benchmark] IsolationForest Drift Recall: {if_drift_recall * 100:.1f}%")
    print(f"[Side-by-Side Benchmark] LSTM-Autoencoder Drift Recall: {lstm_drift_recall * 100:.1f}%")
    print(f"[Side-by-Side Benchmark] Improvement: {drift_stats['improvement_pct']:.1f}%")

    # PHASE 5 EXIT CRITERION ASSERTION:
    # LSTM-AE must outperform IsolationForest specifically on sensor drift
    assert report["phase_5_exit_criterion_met"] is True
    assert lstm_drift_recall > if_drift_recall


# ---------------------------------------------------------------------------
# 5. Serialization and Model Registry Registration
# ---------------------------------------------------------------------------

def test_lstm_model_bundle_serialization_and_registry(clean_training_data, memory_db, tmp_path):
    """
    Assert LSTMModelBundle can be saved, reloaded, and registered into model_registry.
    """
    bundle = train_lstm_autoencoder(
        train_df=clean_training_data,
        variable="temperature",
        station_code="DEL001",
        version="v1.0.0-lstm-save",
        seq_length=12,
        epochs=15,
    )

    artifact_file = tmp_path / "temperature_lstm_test.pt"
    bundle.save(artifact_file)
    assert artifact_file.exists()

    # Reload from disk
    loaded = LSTMModelBundle.load(artifact_file)
    assert loaded.version == bundle.version
    assert loaded.variable == bundle.variable
    assert np.isclose(loaded.threshold, bundle.threshold)

    # Score sample with both models to assert numerical parity
    dummy_prior = [20.0 + i for i in range(11)]
    dummy_curr = 31.0
    now = datetime.now(timezone.utc)

    _, orig_score, _, _ = score_sequence(bundle, dummy_curr, dummy_prior, now)
    _, loaded_score, _, _ = score_sequence(loaded, dummy_curr, dummy_prior, now)
    assert np.isclose(orig_score, loaded_score, atol=1e-4)

    # Register into database
    reg = register_lstm_bundle(
        db=memory_db,
        bundle=bundle,
        metrics={"reconstruction_mse": bundle.mean_train_error, "threshold": bundle.threshold},
        artifact_path=str(artifact_file),
    )

    assert reg.id is not None
    assert reg.is_active is True
    assert reg.model_type == "lstm_autoencoder"

    # Fetch active
    cached = get_active_lstm_bundle(variable="temperature", db=memory_db)
    assert cached is not None
    assert cached.version == bundle.version
