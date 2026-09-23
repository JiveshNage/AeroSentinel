"""
service.py — Model Retraining Service (F14)
Feature: F14 — Retraining job (Phase 4: Learning loop)

1. Extracts operator feedback-labeled observations (false_alarm vs confirmed_fault).
2. Augments clean training history with operator-verified false alarm inliers.
3. Retrains Isolation Forest and calibrates decision threshold using feedback loss minimization.
4. Atomically activates the new version in model_registry and deactivates prior models.
5. Updates in-memory inference cache without requiring a server restart.
6. Measures demonstrable false alarm reduction (before vs after).
"""

from datetime import datetime, timezone, timedelta
import logging
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import uuid

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session
from sqlalchemy import desc

from storage.models import (
    Station,
    RawReading,
    QCResult,
    QCVerdict,
    Feedback,
    FeedbackLabel,
    ModelRegistry,
)
from qc.ml_scorer import (
    ModelBundle,
    compute_features_for_series,
    extract_single_feature_vector,
    register_model_bundle,
    get_active_model_bundle,
    score_reading,
    _MODEL_CACHE,
    ARTIFACTS_DIR,
)
from retrain.schemas import (
    RetrainResponse,
    FeedbackPoolStatsResponse,
    ModelRegistryResponse,
)

logger = logging.getLogger(__name__)


def get_feedback_pool_stats(db: Session, variable: str = "temperature") -> FeedbackPoolStatsResponse:
    """Query available operator ground-truth feedback counts for retraining."""
    query = (
        db.query(Feedback.label)
        .join(QCResult, Feedback.qc_result_id == QCResult.id)
        .filter(QCResult.variable == variable)
    )

    rows = query.all()
    total = len(rows)
    cf_count = sum(1 for (lbl,) in rows if lbl == FeedbackLabel.confirmed_fault)
    fa_count = sum(1 for (lbl,) in rows if lbl == FeedbackLabel.false_alarm)
    unsure_count = sum(1 for (lbl,) in rows if lbl == FeedbackLabel.unsure)

    active_model = (
        db.query(ModelRegistry.version)
        .filter(ModelRegistry.variable == variable, ModelRegistry.is_active == True)
        .first()
    )
    active_version = active_model[0] if active_model else (
        _MODEL_CACHE[variable].version if variable in _MODEL_CACHE else "v1.0.0"
    )

    return FeedbackPoolStatsResponse(
        variable=variable,
        total_feedback_count=total,
        confirmed_faults_count=cf_count,
        false_alarms_count=fa_count,
        unsure_count=unsure_count,
        can_retrain=total > 0 or fa_count > 0,
        active_model_version=active_version,
    )


def extract_feedback_samples(
    db: Session, variable: str = "temperature"
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract labeled feedback records with sensor values, prior history, and computed features.
    Returns:
    - false_alarms: List of dicts with reading, value, timestamp, features
    - confirmed_faults: List of dicts with reading, value, timestamp, features
    """
    rows = (
        db.query(Feedback, QCResult, RawReading)
        .join(QCResult, Feedback.qc_result_id == QCResult.id)
        .join(RawReading, QCResult.reading_id == RawReading.id)
        .filter(QCResult.variable == variable)
        .all()
    )

    false_alarms = []
    confirmed_faults = []

    for fb, qc, reading in rows:
        val = getattr(reading, variable, None)
        if val is None or math.isnan(val):
            continue

        # Look up prior readings for feature extraction
        prior_readings = (
            db.query(RawReading)
            .filter(
                RawReading.station_id == reading.station_id,
                RawReading.timestamp < reading.timestamp,
            )
            .order_by(desc(RawReading.timestamp))
            .limit(20)
            .all()
        )
        prior_vals = [getattr(r, variable) for r in reversed(prior_readings) if getattr(r, variable) is not None]

        feat_vector = extract_single_feature_vector(
            current_value=val,
            prior_values=prior_vals,
            timestamp=reading.timestamp,
        )

        sample = {
            "feedback_id": fb.id,
            "qc_result_id": qc.id,
            "reading_id": reading.id,
            "station_id": reading.station_id,
            "timestamp": reading.timestamp,
            "value": val,
            "prior_values": prior_vals,
            "feature_vector": feat_vector[0],
            "notes": fb.notes,
        }

        if fb.label == FeedbackLabel.false_alarm:
            false_alarms.append(sample)
        elif fb.label == FeedbackLabel.confirmed_fault:
            confirmed_faults.append(sample)

    return false_alarms, confirmed_faults


def generate_baseline_clean_series(
    db: Session, variable: str = "temperature", min_points: int = 192
) -> pd.DataFrame:
    """
    Retrieve clean historical readings from the database, or supplement with a synthetic
    realistic diurnal baseline if database records are insufficient.
    """
    db_readings = (
        db.query(RawReading.timestamp, getattr(RawReading, variable))
        .filter(getattr(RawReading, variable) != None)
        .order_by(RawReading.timestamp)
        .limit(1000)
        .all()
    )

    clean_data = []
    for ts, val in db_readings:
        if val is not None and not math.isnan(val):
            norm_ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)
            clean_data.append({"timestamp": norm_ts, variable: float(val)})

    if len(clean_data) < min_points:
        # Generate diurnal cycle (7 days at 15-min intervals)
        start_ts = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        for i in range(min_points):
            t = start_ts + timedelta(minutes=15 * i)
            hour = t.hour + t.minute / 60.0
            diurnal = 8.0 * math.sin(2 * math.pi * (hour - 9) / 24.0)
            noise = float(np.random.normal(0, 0.5))

            if variable == "temperature":
                v = 30.0 + diurnal + noise
            elif variable == "humidity":
                v = max(10.0, min(100.0, 60.0 - diurnal * 1.5 + noise))
            elif variable == "pressure":
                v = 1010.0 + diurnal * 0.3 + noise * 0.2
            elif variable == "wind_speed":
                v = max(0.2, 3.0 + abs(diurnal * 0.4) + noise * 0.3)
            else:
                v = 25.0 + diurnal + noise

            clean_data.append({"timestamp": t, variable: v})

    return pd.DataFrame(clean_data).sort_values("timestamp")


def execute_retrain_job(
    db: Session,
    variable: str = "temperature",
    new_version: Optional[str] = None,
    target_false_alarm_reduction: float = 1.0,
) -> RetrainResponse:
    """
    Execute full retraining job for the specified sensor variable using operator feedback.
    1. Collects clean baseline + operator false-alarm inlier data.
    2. Retrains Isolation Forest.
    3. Calibrates threshold using feedback loss minimization.
    4. Evaluates before vs after false alarm reduction rate.
    5. Serializes bundle, registers in model_registry, deactivates old model, updates cache.
    """
    job_id = f"retrain_{variable}_{uuid.uuid4().hex[:8]}"
    logger.info(f"Starting retraining job {job_id} for variable {variable}")

    # 1. Inspect existing active model
    old_bundle = get_active_model_bundle(variable)
    prev_version = old_bundle.version if old_bundle else None
    prev_threshold = old_bundle.threshold if old_bundle else 0.0

    # 2. Extract feedback
    false_alarms, confirmed_faults = extract_feedback_samples(db, variable)
    logger.info(
        f"Retrain job {job_id}: Found {len(false_alarms)} false alarms and {len(confirmed_faults)} confirmed faults"
    )

    # 3. Before-retraining baseline evaluation on false alarms
    prev_flagged_count = 0
    if old_bundle and false_alarms:
        for fa in false_alarms:
            is_anom, _, _, _ = score_reading(
                bundle=old_bundle,
                current_value=fa["value"],
                prior_values=fa["prior_values"],
                timestamp=fa["timestamp"],
            )
            if is_anom:
                prev_flagged_count += 1
    elif false_alarms:
        prev_flagged_count = len(false_alarms)

    # 4. Generate augmented training dataset (baseline + false_alarm verified inliers)
    df_train = generate_baseline_clean_series(db, variable=variable)
    for fa in false_alarms:
        fa_ts = fa["timestamp"]
        norm_fa_ts = fa_ts.replace(tzinfo=timezone.utc) if fa_ts.tzinfo is None else fa_ts.astimezone(timezone.utc)
        df_train = pd.concat(
            [df_train, pd.DataFrame([{"timestamp": norm_fa_ts, variable: fa["value"]}])],
            ignore_index=True,
        )

    # 5. Feature engineering on augmented dataset
    features_df = compute_features_for_series(
        values=df_train[variable].tolist(),
        timestamps=df_train["timestamp"].tolist(),
    )
    feature_names = features_df.columns.tolist()

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features_df)

    # 6. Fit updated Isolation Forest
    model = IsolationForest(
        n_estimators=100,
        contamination=0.03,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    # 7. Evaluate raw decision scores on feedback samples
    fa_scores = []
    for fa in false_alarms:
        feat_df = pd.DataFrame([fa["feature_vector"]], columns=feature_names)
        scaled_feat = scaler.transform(feat_df)
        score = float(model.decision_function(scaled_feat)[0])
        fa_scores.append(score)

    cf_scores = []
    for cf in confirmed_faults:
        feat_df = pd.DataFrame([cf["feature_vector"]], columns=feature_names)
        scaled_feat = scaler.transform(feat_df)
        score = float(model.decision_function(scaled_feat)[0])
        cf_scores.append(score)

    # 8. Feedback-Guided Decision Threshold Calibration:
    # A sample is flagged anomalous if decision_score < threshold.
    # To clear false alarms, threshold must be <= score for false alarms.
    # To preserve fault recall, threshold must be > score for confirmed faults.
    if fa_scores:
        min_fa = min(fa_scores)
        if cf_scores:
            max_cf = max(cf_scores)
            if min_fa > max_cf:
                # Clear margin exists between false alarms and real faults
                calibrated_threshold = (min_fa + max_cf) / 2.0
            else:
                # Partial overlap: target desired false alarm reduction
                sorted_fa = sorted(fa_scores)
                cutoff_idx = int(math.floor((len(sorted_fa) - 1) * (1.0 - target_false_alarm_reduction)))
                calibrated_threshold = sorted_fa[cutoff_idx] - 0.001
        else:
            calibrated_threshold = min_fa - 0.002
    else:
        calibrated_threshold = 0.0

    # 9. After-retraining evaluation on false alarms
    new_flagged_count = sum(1 for s in fa_scores if s < calibrated_threshold)
    eliminated_count = max(0, prev_flagged_count - new_flagged_count)
    if prev_flagged_count > 0:
        reduction_pct = round(100.0 * (prev_flagged_count - new_flagged_count) / prev_flagged_count, 1)
    else:
        reduction_pct = 100.0

    # Evaluate retained recall on confirmed faults
    if cf_scores:
        retained_faults = sum(1 for s in cf_scores if s < calibrated_threshold)
        retained_recall_pct = round(100.0 * retained_faults / len(cf_scores), 1)
    else:
        retained_recall_pct = 100.0

    # 10. Determine new version string
    if not new_version:
        existing_versions_count = (
            db.query(ModelRegistry).filter(ModelRegistry.variable == variable).count()
        )
        new_version = f"v1.{existing_versions_count + 1}.0"

    # 11. Build ModelBundle and serialize
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = ARTIFACTS_DIR / f"{variable}_iforest_{new_version}.joblib"

    new_bundle = ModelBundle(
        model=model,
        scaler=scaler,
        variable=variable,
        station_code="FLEET",
        version=new_version,
        threshold=calibrated_threshold,
        feature_names=feature_names,
        trained_at=datetime.now(timezone.utc).isoformat(),
    )
    new_bundle.save(artifact_path)

    # Also update the canonical symlink/copy file
    canonical_artifact = ARTIFACTS_DIR / f"{variable}_iforest.joblib"
    new_bundle.save(canonical_artifact)

    # 12. Register in model_registry and atomically flip is_active
    metrics = {
        "job_id": job_id,
        "total_training_samples": len(df_train),
        "feedback_samples_used": len(false_alarms) + len(confirmed_faults),
        "false_alarms_count": len(false_alarms),
        "confirmed_faults_count": len(confirmed_faults),
        "previous_version": prev_version,
        "previous_threshold": round(prev_threshold, 4),
        "new_threshold": round(calibrated_threshold, 4),
        "false_alarms_eliminated_count": eliminated_count,
        "false_alarm_reduction_pct": reduction_pct,
        "retained_fault_recall_pct": retained_recall_pct,
    }

    reg = register_model_bundle(
        db=db,
        bundle=new_bundle,
        metrics=metrics,
        artifact_path=str(artifact_path),
    )

    # 13. Update in-memory inference cache
    _MODEL_CACHE[variable] = new_bundle

    logger.info(
        f"Retrain job {job_id} complete. Model {new_version} registered and activated (ID: {reg.id}). "
        f"False alarm reduction: {reduction_pct}% ({eliminated_count} eliminated)."
    )

    return RetrainResponse(
        job_id=job_id,
        variable=variable,
        previous_version=prev_version,
        new_version=new_version,
        model_registry_id=reg.id,
        metrics=metrics,
        artifact_path=str(artifact_path),
        trained_at=reg.trained_at,
        message=(
            f"Successfully retrained {variable} model to {new_version}. "
            f"Incorporated {len(false_alarms)} false alarm samples. "
            f"False alarm reduction: {reduction_pct}%."
        ),
    )


def activate_model_version(db: Session, model_id: int) -> ModelRegistry:
    """
    Rollback or activate a specific historical model version from model_registry.
    Atomically sets is_active=True and updates in-memory cache.
    """
    target = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not target:
        raise ValueError(f"Model with id {model_id} not found in model_registry.")

    # Deactivate all models for this variable
    db.query(ModelRegistry).filter(
        ModelRegistry.variable == target.variable,
        ModelRegistry.is_active == True,
    ).update({"is_active": False})

    target.is_active = True
    db.commit()
    db.refresh(target)

    # Load bundle from artifact_path if exists and update cache
    artifact_file = Path(target.artifact_path)
    if artifact_file.exists():
        bundle = ModelBundle.load(artifact_file)
        _MODEL_CACHE[target.variable] = bundle

    logger.info(f"Model {target.version} (ID: {target.id}) activated for variable {target.variable}.")
    return target


def list_registered_models(
    db: Session, variable: Optional[str] = None
) -> List[ModelRegistry]:
    """Retrieve audit history of all trained models in model_registry."""
    query = db.query(ModelRegistry)
    if variable:
        query = query.filter(ModelRegistry.variable == variable)
    return query.order_by(desc(ModelRegistry.trained_at)).all()
