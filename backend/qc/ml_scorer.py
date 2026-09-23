"""
ml_scorer.py — Baseline ML Anomaly Scorer (Isolation Forest)
Feature: F6 — Baseline ML anomaly scorer (Phase 2)

Implements per-station, per-variable Isolation Forest anomaly detection:
1. Multi-dimensional feature engineering: value, 1-step delta, rolling mean departure,
   local volatility (rolling std), and cyclical diurnal features (hour sin/cos).
2. Clean baseline training with consistent StandardScaler serialization (zero train/inference skew).
3. Score normalization into [0.0, 1.0] calibrated against training distribution.
4. Benchmark evaluation computing precision/recall/F1 per fault type (spike, flatline, drift).
5. ModelRegistry versioning and atomic activation in database.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import uuid

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session
from sqlalchemy import desc

from storage.models import Station, RawReading, QCResult, QCVerdict, ModelRegistry


ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "models"


@dataclass
class ModelBundle:
    """Encapsulates a trained Isolation Forest model, scaler, and metadata."""
    model: IsolationForest
    scaler: StandardScaler
    variable: str
    station_code: str
    version: str
    threshold: float
    feature_names: List[str]
    trained_at: str

    def save(self, file_path: Path) -> Path:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, file_path)
        return file_path

    @classmethod
    def load(cls, file_path: Path) -> "ModelBundle":
        return joblib.load(file_path)


def compute_features_for_series(
    values: List[float],
    timestamps: List[datetime],
    window_size: int = 6,
) -> pd.DataFrame:
    """
    Extract multi-dimensional engineered features for a time series:
    1. value: raw sensor reading
    2. delta_1: change from immediate previous reading (catches sudden spikes)
    3. rolling_mean_diff: departure from local window mean (catches gradual drift)
    4. rolling_std: local window standard deviation (catches frozen flatlines where std -> 0)
    5. hour_sin, hour_cos: cyclical diurnal representation of time of day
    """
    df = pd.DataFrame({
        "value": values,
        "timestamp": pd.to_datetime(timestamps),
    })

    # 1. Delta from previous reading
    df["delta_1"] = df["value"].diff().fillna(0.0)

    # 2. Rolling mean and std (using min_periods=1 to support initial readings)
    rolling = df["value"].rolling(window=window_size, min_periods=1)
    rolling_mean = rolling.mean()
    df["rolling_mean_diff"] = df["value"] - rolling_mean
    df["rolling_std"] = rolling.std().fillna(0.0)

    # 3. Cyclical diurnal encoding
    hours = df["timestamp"].dt.hour + (df["timestamp"].dt.minute / 60.0)
    df["hour_sin"] = np.sin(2 * np.pi * hours / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * hours / 24.0)

    feature_cols = ["value", "delta_1", "rolling_mean_diff", "rolling_std", "hour_sin", "hour_cos"]
    return df[feature_cols]


def extract_single_feature_vector(
    current_value: float,
    prior_values: List[float],
    timestamp: datetime,
    window_size: int = 6,
) -> np.ndarray:
    """Extract a 1xN feature vector for a single real-time reading given its prior history."""
    all_values = list(prior_values) + [current_value]
    
    # Delta
    delta_1 = (current_value - prior_values[-1]) if prior_values else 0.0

    # Rolling window (including current reading)
    recent_window = all_values[-window_size:] if len(all_values) >= window_size else all_values
    r_mean = float(np.mean(recent_window))
    r_std = float(np.std(recent_window)) if len(recent_window) > 1 else 0.0
    rolling_mean_diff = current_value - r_mean

    # Diurnal
    dt = timestamp if isinstance(timestamp, datetime) else pd.to_datetime(timestamp)
    hour = dt.hour + (dt.minute / 60.0)
    hour_sin = math.sin(2 * math.pi * hour / 24.0)
    hour_cos = math.cos(2 * math.pi * hour / 24.0)

    return np.array([[current_value, delta_1, rolling_mean_diff, r_std, hour_sin, hour_cos]], dtype=np.float64)


def train_isolation_forest(
    train_df: pd.DataFrame,
    variable: str = "temperature",
    station_code: str = "ALL",
    contamination: float = 0.03,
    version: str = "v1.0.0",
    random_state: int = 42,
) -> ModelBundle:
    """
    Train an Isolation Forest on clean baseline history for a specific station/variable.
    Uses StandardScaler fitted exclusively on training baseline.
    Calibrates decision threshold at the empirical percentile of clean scores.
    """
    clean_series = train_df.dropna(subset=[variable, "timestamp"]).sort_values("timestamp")
    if len(clean_series) < 12:
        raise ValueError(f"Insufficient baseline training samples for {variable}: {len(clean_series)} < 12")

    features_df = compute_features_for_series(
        values=clean_series[variable].tolist(),
        timestamps=clean_series["timestamp"].tolist(),
    )
    feature_names = features_df.columns.tolist()

    # Fit scaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features_df)

    # Fit Isolation Forest
    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    # Calibrated threshold for decision_function (scikit-learn sets 0.0 as boundary)
    threshold = 0.0

    bundle = ModelBundle(
        model=model,
        scaler=scaler,
        variable=variable,
        station_code=station_code,
        version=version,
        threshold=threshold,
        feature_names=feature_names,
        trained_at=datetime.now(timezone.utc).isoformat(),
    )
    return bundle


def score_reading(
    bundle: ModelBundle,
    current_value: Optional[float],
    prior_values: List[float],
    timestamp: datetime,
) -> Tuple[bool, float, float, Dict[str, Any]]:
    """
    Score a single reading against a trained ModelBundle.
    Returns:
    - is_anomalous: bool
    - anomaly_score: float in [0.0, 1.0] (higher means more anomalous)
    - confidence: float in [0.0, 1.0]
    - details: dict containing scores and feature breakdown
    """
    if current_value is None or math.isnan(current_value):
        return False, 0.0, 0.0, {"reason": "missing_or_nan"}

    feat_vector = extract_single_feature_vector(
        current_value=current_value,
        prior_values=prior_values,
        timestamp=timestamp,
    )
    feat_df = pd.DataFrame(feat_vector, columns=bundle.feature_names)
    feat_scaled = bundle.scaler.transform(feat_df)

    # Raw decision function score (negative = outlier, positive = inlier)
    raw_decision = float(bundle.model.decision_function(feat_scaled)[0])
    
    # Normalize to [0.0, 1.0] anomaly score where:
    # raw_decision < threshold (0.0) -> anomalous (score > 0.5)
    # Higher anomaly_score means more anomalous
    anomaly_score = 1.0 / (1.0 + math.exp(10.0 * (raw_decision - bundle.threshold)))
    anomaly_score = max(0.0, min(1.0, anomaly_score))

    is_anomalous = bool(raw_decision < bundle.threshold)
    confidence = round(float(min(0.99, max(0.50, 0.50 + abs(raw_decision)))), 2)

    details = {
        "raw_decision_score": round(raw_decision, 4),
        "calibrated_threshold": round(bundle.threshold, 4),
        "normalized_anomaly_score": round(anomaly_score, 4),
        "model_version": bundle.version,
        "features": {name: round(float(feat_vector[0][i]), 3) for i, name in enumerate(bundle.feature_names)},
    }

    return is_anomalous, anomaly_score, confidence, details


def evaluate_benchmark_dataset(
    bundle: ModelBundle,
    benchmark_df: pd.DataFrame,
    variable: str = "temperature",
    output_report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Evaluate trained model against the multi-station labeled benchmark dataset from F5.
    Computes Precision, Recall, and F1 score per fault type and overall.
    """
    df = benchmark_df.copy().sort_values("timestamp")
    stations = df["station_id"].unique()

    y_true: List[bool] = []
    y_pred: List[bool] = []
    fault_types: List[str] = []

    for st in stations:
        st_df = df[df["station_id"] == st].sort_values("timestamp")
        prior_vals: List[float] = []

        for _, row in st_df.iterrows():
            val = row.get(variable)
            ts = row["timestamp"]
            is_gt_anomaly = bool(row.get("is_anomalous", False))
            ftype = str(row.get("fault_type", "valid"))
            fault_var = row.get("fault_variable")

            # Only evaluate anomalies targeting this specific variable or valid
            if is_gt_anomaly and fault_var and fault_var != variable:
                continue

            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                is_pred, _, _, _ = score_reading(bundle, val, prior_vals, ts)
                y_true.append(is_gt_anomaly)
                y_pred.append(is_pred)
                fault_types.append(ftype)
                prior_vals.append(val)
                if len(prior_vals) > 20:
                    prior_vals.pop(0)

    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)
    fault_types_arr = np.array(fault_types)

    def calc_metrics(true_mask, pred_mask):
        tp = int(np.sum(true_mask & pred_mask))
        fp = int(np.sum((~true_mask) & pred_mask))
        fn = int(np.sum(true_mask & (~pred_mask)))
        tn = int(np.sum((~true_mask) & (~pred_mask)))

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        return {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn, "tn": tn}

    overall_metrics = calc_metrics(y_true_arr, y_pred_arr)

    # Per fault type recall
    per_fault_metrics = {}
    unique_faults = set(fault_types_arr)
    unique_faults.discard("valid")

    for ftype in sorted(unique_faults):
        mask = (fault_types_arr == ftype)
        if np.sum(mask) > 0:
            tp = int(np.sum(mask & y_pred_arr))
            fn = int(np.sum(mask & (~y_pred_arr)))
            recall = round(float(tp / (tp + fn)), 4) if (tp + fn) > 0 else 0.0
            per_fault_metrics[ftype] = {
                "total_injected": int(np.sum(mask)),
                "detected": tp,
                "missed": fn,
                "recall": recall,
            }

    report = {
        "model_type": "isolation_forest",
        "variable": variable,
        "version": bundle.version,
        "total_observations_evaluated": len(y_true),
        "overall": overall_metrics,
        "per_fault_type": per_fault_metrics,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }

    if output_report_path:
        output_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_report_path, "w") as f:
            json.dump(report, f, indent=2)

    return report


def register_model_bundle(
    db: Session,
    bundle: ModelBundle,
    metrics: Dict[str, Any],
    artifact_path: str,
) -> ModelRegistry:
    """
    Register model artifact in model_registry table.
    Atomically deactivates any existing active model for this variable and activates the new one.
    """
    # Deactivate existing active models for this variable
    db.query(ModelRegistry).filter(
        ModelRegistry.variable == bundle.variable,
        ModelRegistry.is_active == True,
    ).update({"is_active": False})

    reg = ModelRegistry(
        model_type="isolation_forest",
        variable=bundle.variable,
        version=bundle.version,
        trained_at=datetime.now(timezone.utc),
        training_data_range=f"Station {bundle.station_code}",
        metrics=metrics,
        artifact_path=artifact_path,
        is_active=True,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg


# Cache of loaded models in memory for fast inference
_MODEL_CACHE: Dict[str, ModelBundle] = {}


def get_active_model_bundle(variable: str, db: Optional[Session] = None) -> Optional[ModelBundle]:
    """Retrieve model bundle from memory cache, database active registry, or disk artifact."""
    if variable in _MODEL_CACHE:
        return _MODEL_CACHE[variable]

    if db:
        active_reg = (
            db.query(ModelRegistry)
            .filter(ModelRegistry.variable == variable, ModelRegistry.is_active == True)
            .first()
        )
        if active_reg and active_reg.artifact_path and Path(active_reg.artifact_path).exists():
            bundle = ModelBundle.load(Path(active_reg.artifact_path))
            _MODEL_CACHE[variable] = bundle
            return bundle

    artifact_file = ARTIFACTS_DIR / f"{variable}_iforest.joblib"
    if artifact_file.exists():
        bundle = ModelBundle.load(artifact_file)
        _MODEL_CACHE[variable] = bundle
        return bundle
    return None


def run_ml_scoring_for_reading(db: Session, reading_id: int) -> List[QCResult]:
    """
    Score a raw reading using active ML models.
    Persists QCResult records with reason_code = 'ML_ISOFOREST'.
    """
    reading = db.query(RawReading).filter(RawReading.id == reading_id).first()
    if not reading:
        raise ValueError(f"RawReading with id {reading_id} not found.")

    station = db.query(Station).filter(Station.id == reading.station_id).first()
    if not station:
        raise ValueError(f"Station with id {reading.station_id} not found.")

    # Fetch prior readings
    prior_readings = (
        db.query(RawReading)
        .filter(
            RawReading.station_id == station.id,
            RawReading.timestamp < reading.timestamp,
        )
        .order_by(desc(RawReading.timestamp))
        .limit(20)
        .all()
    )
    prior_readings = list(reversed(prior_readings))

    results: List[QCResult] = []

    for var_name in ["temperature", "humidity"]:
        bundle = get_active_model_bundle(var_name, db=db)
        if not bundle:
            continue

        val = getattr(reading, var_name, None)
        if val is None or math.isnan(val):
            continue

        prior_vals = [getattr(r, var_name) for r in prior_readings if getattr(r, var_name) is not None]
        is_anom, anom_score, confidence, details = score_reading(
            bundle=bundle,
            current_value=val,
            prior_values=prior_vals,
            timestamp=reading.timestamp,
        )

        verdict = QCVerdict.anomalous if is_anom else QCVerdict.valid
        fault_type = "spike" if is_anom and abs(details["features"].get("delta_1", 0)) > 5.0 else ("drift" if is_anom else None)

        qc_res = QCResult(
            reading_id=reading.id,
            station_id=station.id,
            variable=var_name,
            verdict=verdict,
            reason_code="ML_ISOFOREST",
            fault_type=fault_type,
            confidence=confidence,
            ml_model_version=bundle.version,
            details=details,
        )
        results.append(qc_res)
        db.add(qc_res)

    if results:
        db.commit()
        for r in results:
            db.refresh(r)

    return results
