"""
classifier.py — Fault Classifier (Merge Layer) for AeroSentinel QC Pipeline
Feature: F8 — Fault classifier (Phase 2)

Merges diagnostic signals from:
1. Rule-based checks (F4): Range bounds, circular step changes, flatlines.
2. ML Anomaly Scorer (F6): Isolation Forest reconstruction error and calibrated anomaly scores.
3. Spatial Consistency Checker (F7): Contemporaneous cross-station neighbor validation.

Produces a unified, explainable verdict (valid | suspect | anomalous), fault_type,
reason_code, and confidence score, logged to the qc_results table.
"""

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import uuid

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import desc

from storage.models import Station, RawReading, QCResult, QCVerdict
from qc.rules import evaluate_reading_rules, MONITORED_VARIABLES
from qc.ml_scorer import get_active_model_bundle, score_reading
from qc.spatial import evaluate_spatial_for_reading


def classify_verdict(
    variable: str,
    rule_verdict: Optional[QCVerdict] = None,
    rule_reason: Optional[str] = None,
    rule_fault_type: Optional[str] = None,
    rule_details: Optional[Dict[str, Any]] = None,
    ml_is_anom: bool = False,
    ml_score: float = 0.0,
    ml_confidence: float = 0.5,
    ml_details: Optional[Dict[str, Any]] = None,
    spatial_is_anom: bool = False,
    spatial_reason: Optional[str] = None,
    spatial_details: Optional[Dict[str, Any]] = None,
) -> Tuple[QCVerdict, Optional[str], str, float, Dict[str, Any]]:
    """
    Deterministic merge decision matrix.
    Returns:
    - verdict: QCVerdict (valid | suspect | anomalous)
    - fault_type: Optional[str] (spike | flatline | drift | dropout | spatial_inconsistency | plausible_extreme)
    - reason_code: str
    - confidence: float in [0.0, 1.0]
    - details: combined explanation dictionary
    """
    merged_details = {
        "variable": variable,
        "rule": {"verdict": str(rule_verdict) if rule_verdict else None, "reason": rule_reason, "details": rule_details},
        "ml": {"is_anom": ml_is_anom, "score": round(ml_score, 4), "confidence": round(ml_confidence, 2), "details": ml_details},
        "spatial": {"is_anom": spatial_is_anom, "reason": spatial_reason, "details": spatial_details},
    }

    # 1. Critical Rule Range Failure (Physical Impossibility)
    if rule_reason == "RULE_RANGE_FAIL":
        return QCVerdict.anomalous, "spike", "RULE_RANGE", 0.99, merged_details

    # 2. Critical Rule Persistence Failure (Sensor Freeze / Flatline)
    if rule_reason == "RULE_PERSISTENCE_FAIL":
        return QCVerdict.anomalous, "flatline", "RULE_FLATLINE", 0.98, merged_details

    # 3. Rule Step Failure (Abrupt Jump)
    if rule_reason == "RULE_STEP_FAIL":
        # Check if spatial neighbors also jumped simultaneously (regional squall / gust front)
        if spatial_reason == "SPATIAL_CONSISTENT":
            # Genuine regional extreme weather event confirmed by neighbors
            return QCVerdict.valid, "plausible_extreme", "SPATIAL_OVERRIDE_EXTREME", 0.88, merged_details
        else:
            # Isolated abrupt jump unconfirmed by neighbors -> sensor spike
            return QCVerdict.anomalous, "spike", "RULE_STEP", 0.95, merged_details

    # 4. ML Anomaly + Spatial Cross-Validation
    if ml_is_anom:
        if spatial_is_anom:
            # Both ML and Spatial agree: this station is a strong outlier!
            # If step/delta is small but accumulating, it's drift; otherwise spike
            delta = abs(ml_details.get("features", {}).get("delta_1", 0.0)) if ml_details else 0.0
            fault_type = "drift" if delta < 4.0 else "spike"
            confidence = min(0.98, max(ml_confidence, 0.88))
            return QCVerdict.anomalous, fault_type, "ML_AND_SPATIAL_CONFIRMED", confidence, merged_details

        elif spatial_reason == "SPATIAL_CONSISTENT":
            # Key SIH Differentiator: ML flagged unusual tail, but neighboring AWS verify
            # that the entire regional cluster is undergoing the same event (e.g. record heatwave)!
            return QCVerdict.valid, "plausible_extreme", "SPATIAL_VALIDATED_EXTREME", 0.92, merged_details

        else:
            # Spatial data unavailable or insufficient (e.g. isolated station)
            if ml_score >= 0.75:
                return QCVerdict.anomalous, "drift", "ML_ISOFOREST", ml_confidence, merged_details
            else:
                return QCVerdict.suspect, "drift", "ML_BORDERLINE", 0.65, merged_details

    # 5. Spatial Mismatch Alone (Station diverges from neighbors even within range bounds)
    if spatial_is_anom:
        return QCVerdict.anomalous, "spatial_inconsistency", "SPATIAL_MISMATCH", 0.92, merged_details

    # 6. Borderline check: if ML score is elevated (0.50 - 0.65) with no spatial confirmation
    if ml_score >= 0.55:
        if spatial_reason == "SPATIAL_CONSISTENT":
            return QCVerdict.valid, None, "VALID_READING", 0.95, merged_details
        else:
            return QCVerdict.suspect, None, "ML_SUSPECT", 0.60, merged_details

    # 7. Clean across all layers
    return QCVerdict.valid, None, "VALID_READING", 1.0, merged_details


def run_full_qc_pipeline_for_reading(
    db: Session,
    reading_id: int,
) -> List[QCResult]:
    """
    Executes the complete multi-tier QC pipeline for a single raw reading:
    1. Tier 1: Deterministic rules (range, circular step, persistence).
    2. Tier 2: Isolation Forest statistical ML scoring (per active variable).
    3. Tier 3: Cross-station spatial consistency check against k-nearest neighbors.
    4. Tier 4: Merge classification into unified verdict and persist to qc_results.
    """
    reading = db.query(RawReading).filter(RawReading.id == reading_id).first()
    if not reading:
        raise ValueError(f"RawReading with id {reading_id} not found.")

    station = db.query(Station).filter(Station.id == reading.station_id).first()
    if not station:
        raise ValueError(f"Station with id {reading.station_id} not found.")

    # 1. Fetch prior reading history
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

    # Tier 1: Rules
    rule_results = evaluate_reading_rules(
        reading=reading,
        station=station,
        recent_readings=prior_readings,
    )
    rules_by_var = {r.variable: r for r in rule_results}

    merged_results: List[QCResult] = []

    for var_name in MONITORED_VARIABLES:
        val = getattr(reading, var_name, None)
        if val is None or math.isnan(val):
            continue

        r_res = rules_by_var.get(var_name)

        # Tier 2: ML Scorer
        ml_bundle = get_active_model_bundle(var_name)
        ml_is_anom, ml_score, ml_conf, ml_details = False, 0.0, 0.5, {}
        ml_version = None
        if ml_bundle:
            ml_version = ml_bundle.version
            prior_vals = [getattr(pr, var_name) for pr in prior_readings if getattr(pr, var_name) is not None]
            ml_is_anom, ml_score, ml_conf, ml_details = score_reading(
                bundle=ml_bundle,
                current_value=val,
                prior_values=prior_vals,
                timestamp=reading.timestamp,
            )

        # Tier 3: Spatial Consistency
        spatial_res = evaluate_spatial_for_reading(
            db=db,
            reading=reading,
            station=station,
            variable=var_name,
        )
        sp_is_anom = (spatial_res.verdict == QCVerdict.anomalous) if spatial_res else False
        sp_reason = spatial_res.reason_code if spatial_res else "SPATIAL_INSUFFICIENT_DATA"
        sp_details = spatial_res.details if spatial_res else {}

        # Tier 4: Classifier Merge
        verdict, fault_type, reason_code, confidence, details = classify_verdict(
            variable=var_name,
            rule_verdict=r_res.verdict if r_res else None,
            rule_reason=r_res.reason_code if r_res else None,
            rule_fault_type=r_res.fault_type if r_res else None,
            rule_details=r_res.details if r_res else None,
            ml_is_anom=ml_is_anom,
            ml_score=ml_score,
            ml_confidence=ml_conf,
            ml_details=ml_details,
            spatial_is_anom=sp_is_anom,
            spatial_reason=sp_reason,
            spatial_details=sp_details,
        )

        qc_row = QCResult(
            reading_id=reading.id,
            station_id=station.id,
            variable=var_name,
            verdict=verdict,
            reason_code=reason_code,
            fault_type=fault_type,
            confidence=confidence,
            ml_model_version=ml_version,
            details=details,
        )
        merged_results.append(qc_row)
        db.add(qc_row)

    if merged_results:
        db.commit()
        for res in merged_results:
            db.refresh(res)

    return merged_results


def evaluate_classifier_benchmark(
    db: Session,
    benchmark_df: pd.DataFrame,
    variable: str = "temperature",
    output_report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Evaluate the merged classifier pipeline on the multi-station labeled benchmark dataset.
    Computes precision, recall, and F1 score per fault type and overall.
    """
    df = benchmark_df.copy().sort_values("timestamp")
    stations = df["station_id"].unique()

    y_true: List[bool] = []
    y_pred: List[bool] = []
    fault_types: List[str] = []

    # Map station codes to DB station IDs
    all_stations = db.query(Station).all()
    st_code_map = {s.station_code: s for s in all_stations}

    for st_code in stations:
        st_obj = st_code_map.get(st_code)
        if not st_obj:
            continue

        st_rows = df[df["station_id"] == st_code].sort_values("timestamp")
        prior_vals: List[float] = []
        prior_dummy_readings: List[RawReading] = []

        for _, row in st_rows.iterrows():
            val = row.get(variable)
            ts = row["timestamp"]
            is_gt_anomaly = bool(row.get("is_anomalous", False))
            ftype = str(row.get("fault_type", "valid"))
            fault_var = row.get("fault_variable")

            if is_gt_anomaly and fault_var and fault_var != variable:
                continue

            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                # Evaluate rules with recent readings history
                dummy_reading = RawReading(
                    id=999999,
                    station_id=st_obj.id,
                    timestamp=pd.to_datetime(ts),
                    temperature=val if variable == "temperature" else None,
                    humidity=val if variable == "humidity" else None,
                    pressure=1010.0,
                    wind_speed=5.0,
                    wind_direction=180.0,
                    rainfall=0.0,
                    solar_radiation=400.0,
                )
                rule_res = evaluate_reading_rules(dummy_reading, st_obj, recent_readings=prior_dummy_readings)
                r_temp = next((r for r in rule_res if r.variable == variable), None)

                prior_dummy_readings.append(dummy_reading)
                if len(prior_dummy_readings) > 20:
                    prior_dummy_readings.pop(0)

                # Evaluate ML
                ml_bundle = get_active_model_bundle(variable)
                ml_anom, ml_sc, ml_cf, ml_dt = False, 0.0, 0.5, {}
                if ml_bundle:
                    ml_anom, ml_sc, ml_cf, ml_dt = score_reading(ml_bundle, val, prior_vals, pd.to_datetime(ts))

                # Contemporaneous neighbor values from benchmark_df at same timestamp
                same_ts_df = df[(df["timestamp"] == ts) & (df["station_id"] != st_code)]
                neighbor_vals = [float(v) for v in same_ts_df[variable].dropna() if not math.isnan(v)]

                from qc.spatial import check_spatial_consistency
                sp_anom, sp_reason, sp_dt = check_spatial_consistency(
                    target_value=val,
                    neighbor_values=neighbor_vals,
                )

                verdict, out_ftype, rcode, conf, details = classify_verdict(
                    variable=variable,
                    rule_verdict=r_temp.verdict if r_temp else None,
                    rule_reason=r_temp.reason_code if r_temp else None,
                    rule_fault_type=r_temp.fault_type if r_temp else None,
                    rule_details=r_temp.details if r_temp else None,
                    ml_is_anom=ml_anom,
                    ml_score=ml_sc,
                    ml_confidence=ml_cf,
                    ml_details=ml_dt,
                    spatial_is_anom=sp_anom,
                    spatial_reason=sp_reason,
                    spatial_details=sp_dt,
                )

                is_classified_anom = (verdict == QCVerdict.anomalous)
                y_true.append(is_gt_anomaly)
                y_pred.append(is_classified_anom)
                fault_types.append(ftype)

                prior_vals.append(val)
                if len(prior_vals) > 20:
                    prior_vals.pop(0)

    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)
    fault_types_arr = np.array(fault_types)

    tp = int(np.sum(y_true_arr & y_pred_arr))
    fp = int(np.sum((~y_true_arr) & y_pred_arr))
    fn = int(np.sum(y_true_arr & (~y_pred_arr)))
    tn = int(np.sum((~y_true_arr) & (~y_pred_arr)))

    prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

    per_fault_metrics = {}
    unique_faults = set(fault_types_arr)
    unique_faults.discard("valid")

    for ftype in sorted(unique_faults):
        mask = (fault_types_arr == ftype)
        if np.sum(mask) > 0:
            sub_tp = int(np.sum(mask & y_pred_arr))
            sub_fn = int(np.sum(mask & (~y_pred_arr)))
            sub_rec = round(float(sub_tp / (sub_tp + sub_fn)), 4) if (sub_tp + sub_fn) > 0 else 0.0
            per_fault_metrics[ftype] = {
                "total_injected": int(np.sum(mask)),
                "detected": sub_tp,
                "missed": sub_fn,
                "recall": sub_rec,
            }

    report = {
        "pipeline_component": "fault_classifier_merge_layer",
        "variable": variable,
        "total_observations_evaluated": len(y_true),
        "overall": {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
        },
        "per_fault_type": per_fault_metrics,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }

    if output_report_path:
        output_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_report_path, "w") as f:
            json.dump(report, f, indent=2)

    return report
