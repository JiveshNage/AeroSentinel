"""
test_classifier.py — Unit and integration tests for F8 Fault Classifier (Merge Layer)

Tests:
1. Table-driven merge logic: tests all combinations of rule, ML, and spatial signals.
2. Spatial override of ML false positives: validates genuine regional extreme weather invariance.
3. Multi-station benchmark evaluation: computes precision, recall, and F1 across all fault types.
4. Full pipeline execution: verifies database persistence into qc_results.
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
from storage.models import Station, RawReading, QCResult, QCVerdict, StationStatus
from qc.classifier import (
    classify_verdict,
    run_full_qc_pipeline_for_reading,
    evaluate_classifier_benchmark,
)
from qc.fault_injector import generate_labeled_benchmark_dataset
from ingestion.simulator import generate_synthetic_weather_stream


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database for testing classifier merge layer."""
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
# 1. Table-Driven Merge Logic Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rule_verdict,rule_reason,ml_anom,spatial_anom,spatial_reason,expected_verdict,expected_ftype,expected_code",
    [
        # Physical Rule Range Failure: always anomalous spike
        (QCVerdict.anomalous, "RULE_RANGE_FAIL", False, False, "SPATIAL_CONSISTENT", QCVerdict.anomalous, "spike", "RULE_RANGE"),
        # Physical Rule Persistence Failure: always anomalous flatline
        (QCVerdict.anomalous, "RULE_PERSISTENCE_FAIL", False, False, "SPATIAL_CONSISTENT", QCVerdict.anomalous, "flatline", "RULE_FLATLINE"),
        # Rule Step Jump without spatial neighbor agreement: anomalous spike
        (QCVerdict.anomalous, "RULE_STEP_FAIL", False, True, "SPATIAL_MISMATCH", QCVerdict.anomalous, "spike", "RULE_STEP"),
        # Rule Step Jump WITH spatial neighbor agreement (regional squall): valid plausible_extreme
        (QCVerdict.anomalous, "RULE_STEP_FAIL", False, False, "SPATIAL_CONSISTENT", QCVerdict.valid, "plausible_extreme", "SPATIAL_OVERRIDE_EXTREME"),
        # ML Anomaly + Spatial Mismatch: anomalous drift
        (QCVerdict.valid, "VALID_READING", True, True, "SPATIAL_MISMATCH", QCVerdict.anomalous, "drift", "ML_AND_SPATIAL_CONFIRMED"),
        # ML Anomaly + Spatial Consistent (widespread heatwave): valid plausible_extreme
        (QCVerdict.valid, "VALID_READING", True, False, "SPATIAL_CONSISTENT", QCVerdict.valid, "plausible_extreme", "SPATIAL_VALIDATED_EXTREME"),
        # Spatial Mismatch Alone (deviates from neighbors): anomalous spatial_inconsistency
        (QCVerdict.valid, "VALID_READING", False, True, "SPATIAL_MISMATCH", QCVerdict.anomalous, "spatial_inconsistency", "SPATIAL_MISMATCH"),
        # All layers clean: valid reading
        (QCVerdict.valid, "VALID_READING", False, False, "SPATIAL_CONSISTENT", QCVerdict.valid, None, "VALID_READING"),
    ],
)
def test_table_driven_classifier_matrix(
    rule_verdict,
    rule_reason,
    ml_anom,
    spatial_anom,
    spatial_reason,
    expected_verdict,
    expected_ftype,
    expected_code,
):
    verdict, ftype, rcode, conf, details = classify_verdict(
        variable="temperature",
        rule_verdict=rule_verdict,
        rule_reason=rule_reason,
        ml_is_anom=ml_anom,
        ml_score=0.85 if ml_anom else 0.20,
        spatial_is_anom=spatial_anom,
        spatial_reason=spatial_reason,
    )

    assert verdict == expected_verdict
    assert ftype == expected_ftype
    assert rcode == expected_code
    assert 0.5 <= conf <= 1.0


# ---------------------------------------------------------------------------
# 2. Benchmark Evaluation & Precision/Recall Metrics
# ---------------------------------------------------------------------------

def test_evaluate_classifier_benchmark(memory_db, tmp_path):
    """
    Evaluate the merged classifier pipeline on the multi-station labeled benchmark dataset.
    Asserts high recall on all fault types and writes classifier evaluation report.
    """
    # 1. Seed stations in DB
    stations = []
    for i in range(1, 6):
        st = Station(
            id=uuid.uuid4(),
            station_code=f"NCR00{i}",
            name=f"NCR Station {i}",
            latitude=28.5 + (i * 0.05),
            longitude=77.2 + (i * 0.05),
            elevation_m=210.0,
            state="Delhi",
            district="Delhi",
            status=StationStatus.active,
        )
        memory_db.add(st)
        stations.append(st)
    memory_db.commit()

    # 2. Generate benchmark dataset
    base_time = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    clean_stream = generate_synthetic_weather_stream(stations, start_time=base_time, hours=48)
    benchmark_df = generate_labeled_benchmark_dataset(clean_stream, seed=42)

    report_path = tmp_path / "classifier_benchmark_report.json"
    report = evaluate_classifier_benchmark(
        db=memory_db,
        benchmark_df=benchmark_df,
        variable="temperature",
        output_report_path=report_path,
    )

    assert report_path.exists()
    assert "overall" in report
    assert "per_fault_type" in report

    overall = report["overall"]
    assert overall["recall"] >= 0.65
    assert overall["precision"] >= 0.90
    assert overall["f1"] >= 0.75

    per_fault = report["per_fault_type"]
    assert "spike" in per_fault
    assert per_fault["spike"]["recall"] >= 0.90
    assert "flatline" in per_fault
    assert per_fault["flatline"]["recall"] >= 0.60
    assert "drift" in per_fault
    assert per_fault["drift"]["recall"] >= 0.60


# ---------------------------------------------------------------------------
# 3. End-to-End Pipeline Execution & DB Persistence
# ---------------------------------------------------------------------------

def test_run_full_qc_pipeline_for_reading_persistence(memory_db):
    """
    Assert run_full_qc_pipeline_for_reading executes rules, ML, and spatial layers,
    merging results and persisting into qc_results.
    """
    station = Station(
        id=uuid.uuid4(),
        station_code="DEL_PIPELINE",
        name="Delhi Pipeline Test",
        latitude=28.58,
        longitude=77.20,
        elevation_m=216.0,
        state="Delhi",
        district="New Delhi",
        sensor_specs={"temperature": {"min": -10.0, "max": 55.0, "step_max": 8.0}},
        status=StationStatus.active,
    )
    memory_db.add(station)
    memory_db.commit()

    # Reading with range violation (68°C)
    ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    reading = RawReading(
        station_id=station.id,
        timestamp=ts,
        temperature=68.0,  # Range fail
        humidity=50.0,     # Clean
        pressure=1008.0,   # Clean
        wind_speed=4.5,
        wind_direction=180.0,
        rainfall=0.0,
        solar_radiation=450.0,
    )
    memory_db.add(reading)
    memory_db.commit()
    memory_db.refresh(reading)

    results = run_full_qc_pipeline_for_reading(memory_db, reading.id)
    assert len(results) > 0

    # Temperature must be anomalous with RULE_RANGE
    temp_res = next(r for r in results if r.variable == "temperature")
    assert temp_res.verdict == QCVerdict.anomalous
    assert temp_res.reason_code == "RULE_RANGE"
    assert temp_res.fault_type == "spike"
    assert temp_res.confidence >= 0.95

    # Humidity must be valid
    hum_res = next(r for r in results if r.variable == "humidity")
    assert hum_res.verdict == QCVerdict.valid
    assert hum_res.reason_code == "VALID_READING"

    # Query DB to assert rows are saved
    db_rows = memory_db.query(QCResult).filter(QCResult.reading_id == reading.id).all()
    assert len(db_rows) == len(results)
