"""
service.py — Predictive Maintenance Scoring Engine (F16)
Feature: F16 — Predictive Maintenance Scoring (Phase 5 Stretch Goal)

Computes station-level failure risk within the next 30 days based on:
1. Historical anomaly & suspect QC verdict frequencies
2. Monotonic calibration drift accumulation
3. Frozen sensor flatline frequency
4. Unresolved operational alerts & alert severity
5. Telemetry dropout and communication gaps
6. Hardware deployment age

Surfaces a prioritized, ranked failure-risk list and recommended technician actions.
"""

from datetime import datetime, timezone, timedelta, date
import math
from typing import List, Dict, Any, Optional, Tuple
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from storage.models import (
    Station,
    RawReading,
    QCResult,
    QCVerdict,
    Alert,
    AlertStatus,
    AlertSeverity,
    MaintenancePrediction,
)
from maintenance.schemas import (
    MaintenancePredictionResponse,
    FleetMaintenanceSummary,
)


def extract_station_health_features(
    db: Session,
    station: Station,
    lookback_days: int = 30,
) -> Dict[str, Any]:
    """
    Extract multi-channel health metrics and operational fault indicators
    for a single station over the specified lookback window.
    """
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=lookback_days)

    # 1. Total Telemetry Observations
    total_readings = (
        db.query(func.count(RawReading.id))
        .filter(
            RawReading.station_id == station.id,
            RawReading.timestamp >= start_time,
        )
        .scalar()
        or 0
    )

    # 2. QC Anomaly & Suspect Verdict Counts
    anomalous_qc_count = (
        db.query(func.count(QCResult.id))
        .filter(
            QCResult.station_id == station.id,
            QCResult.created_at >= start_time,
            QCResult.verdict == QCVerdict.anomalous,
        )
        .scalar()
        or 0
    )

    suspect_qc_count = (
        db.query(func.count(QCResult.id))
        .filter(
            QCResult.station_id == station.id,
            QCResult.created_at >= start_time,
            QCResult.verdict == QCVerdict.suspect,
        )
        .scalar()
        or 0
    )

    # 3. Specific Fault Types
    drift_fault_count = (
        db.query(func.count(QCResult.id))
        .filter(
            QCResult.station_id == station.id,
            QCResult.created_at >= start_time,
            QCResult.fault_type == "drift",
        )
        .scalar()
        or 0
    )

    flatline_fault_count = (
        db.query(func.count(QCResult.id))
        .filter(
            QCResult.station_id == station.id,
            QCResult.created_at >= start_time,
            QCResult.fault_type == "flatline",
        )
        .scalar()
        or 0
    )

    dropout_fault_count = (
        db.query(func.count(QCResult.id))
        .filter(
            QCResult.station_id == station.id,
            QCResult.created_at >= start_time,
            QCResult.fault_type == "dropout",
        )
        .scalar()
        or 0
    )

    # 4. Operational Alerts
    open_alerts_count = (
        db.query(func.count(Alert.id))
        .filter(
            Alert.station_id == station.id,
            Alert.status == AlertStatus.open,
        )
        .scalar()
        or 0
    )

    critical_alerts_count = (
        db.query(func.count(Alert.id))
        .filter(
            Alert.station_id == station.id,
            Alert.status == AlertStatus.open,
            Alert.severity == AlertSeverity.critical,
        )
        .scalar()
        or 0
    )

    # 5. Station Hardware Age
    install_date = station.install_date
    if install_date:
        if isinstance(install_date, datetime):
            install_date = install_date.date()
        age_days = max(1, (now.date() - install_date).days)
    else:
        age_days = 365

    # Normalized Rates
    effective_readings = max(total_readings, 1)
    anom_rate = min(1.0, anomalous_qc_count / effective_readings)
    suspect_rate = min(1.0, suspect_qc_count / effective_readings)

    return {
        "station_id": str(station.id),
        "station_code": station.station_code,
        "total_readings": total_readings,
        "anomalous_qc_count": anomalous_qc_count,
        "suspect_qc_count": suspect_qc_count,
        "anom_rate": anom_rate,
        "suspect_rate": suspect_rate,
        "drift_fault_count": drift_fault_count,
        "flatline_fault_count": flatline_fault_count,
        "dropout_fault_count": dropout_fault_count,
        "open_alerts_count": open_alerts_count,
        "critical_alerts_count": critical_alerts_count,
        "age_days": age_days,
    }


def calculate_failure_risk(features: Dict[str, Any]) -> Tuple[float, str, str, str, Dict[str, Any]]:
    """
    Calculate 30-day failure probability via calibrated probabilistic reliability function.
    Returns:
    - failure_probability: float in [0.0, 1.0]
    - risk_level: str ("critical" | "elevated" | "moderate" | "nominal")
    - top_driver: str
    - recommended_action: str
    - top_factors: dict of feature contributions and diagnostic metrics
    """
    # If station has no readings at all, flag moderate-elevated risk due to missing telemetry
    if features.get("total_readings", 0) == 0:
        return (
            0.55,
            "elevated",
            "Zero Telemetry Received",
            "Station offline or unpolled. Inspect power supply, solar charge controller, and cellular SIM.",
            {
                "risk_level": "elevated",
                "top_driver": "Zero Telemetry Received",
                "recommended_action": "Station offline. Inspect power supply and modem.",
                "factor_breakdown": {"telemetry_missing": 1.0},
                "metrics_summary": features,
            },
        )

    # Component risk activations (each normalized into ~ [0.0, 1.0])
    # 1. Anomaly & Suspect Rate
    c_anom = min(1.0, (features["anom_rate"] * 6.0) + (features["suspect_rate"] * 2.0))
    # 2. Calibration Drift Intensity
    c_drift = min(1.0, features["drift_fault_count"] / 4.0)
    # 3. Flatline Persistence Freeze
    c_flatline = min(1.0, features["flatline_fault_count"] / 4.0)
    # 4. Open & Critical Alerts
    c_alerts = min(1.0, (features["open_alerts_count"] + 2.0 * features["critical_alerts_count"]) / 4.0)
    # 5. Dropouts / Missing telemetry
    c_dropout = min(1.0, features["dropout_fault_count"] / 3.0)
    # 6. Station Hardware Age (up to 5 years / 1825 days)
    c_age = min(1.0, features["age_days"] / 1825.0)

    # Weights representing failure importance
    w_anom = 3.8
    w_drift = 2.6
    w_flatline = 2.2
    w_alerts = 2.0
    w_dropout = 1.4
    w_age = 0.5

    # Base logit intercept: -2.5 gives clean nominal stations ~7.6% failure baseline
    intercept = -2.50
    z = (
        intercept
        + (w_anom * c_anom)
        + (w_drift * c_drift)
        + (w_flatline * c_flatline)
        + (w_alerts * c_alerts)
        + (w_dropout * c_dropout)
        + (w_age * c_age)
    )

    prob = 1.0 / (1.0 + math.exp(-z))
    # Bound between 2% and 98%
    failure_probability = max(0.02, min(0.98, round(prob, 4)))

    # Categorize Risk Level
    if failure_probability >= 0.70:
        risk_level = "critical"
    elif failure_probability >= 0.40:
        risk_level = "elevated"
    elif failure_probability >= 0.20:
        risk_level = "moderate"
    else:
        risk_level = "nominal"

    # Identify Top Driver
    contributions = {
        "Sensor Drift Accumulation": round(w_drift * c_drift, 3),
        "Sensor Flatline / Freeze": round(w_flatline * c_flatline, 3),
        "High QC Anomaly Rate": round(w_anom * c_anom, 3),
        "Unresolved Diagnostic Alerts": round(w_alerts * c_alerts, 3),
        "Telemetry Dropouts": round(w_dropout * c_dropout, 3),
        "Hardware Lifespan Aging": round(w_age * c_age, 3),
    }

    # Find highest non-zero driver
    sorted_drivers = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)
    if failure_probability <= 0.15 or sorted_drivers[0][1] <= 0.05:
        top_driver = "Nominal Baseline"
        recommended_action = "Subsystems operating nominally. Maintain scheduled routine sensor cleaning."
    else:
        top_driver = sorted_drivers[0][0]
        if top_driver == "Sensor Drift Accumulation":
            recommended_action = "Recalibrate sensor probes: perform zero/span calibration on temperature RTD and capacitive humidity sensors."
        elif top_driver == "Sensor Flatline / Freeze":
            recommended_action = "Inspect sensor transducer bus: test for frozen analog-to-digital converter (ADC) or intermittent power rails."
        elif top_driver == "High QC Anomaly Rate":
            recommended_action = "Priority maintenance dispatch: inspect station for physical damage, lightning surge, or degraded wiring."
        elif top_driver == "Unresolved Diagnostic Alerts":
            recommended_action = "Acknowledge and clear active alerts: dispatch field crew for diagnostic fault resolution."
        elif top_driver == "Telemetry Dropouts":
            recommended_action = "Inspect communications unit: check 4G/GPRS modem antenna, solar battery storage, and SIM connectivity."
        else:
            recommended_action = "Station approaching extended service life: schedule overhaul and component lifecycle replacement."

    top_factors = {
        "risk_level": risk_level,
        "top_driver": top_driver,
        "recommended_action": recommended_action,
        "factor_breakdown": contributions,
        "metrics_summary": features,
    }

    return failure_probability, risk_level, top_driver, recommended_action, top_factors


def recompute_fleet_predictions(db: Session) -> List[MaintenancePredictionResponse]:
    """
    Execute predictive maintenance scoring across all registered stations,
    persisting new records to maintenance_predictions.
    Returns ranked predictions sorted descending by failure probability.
    """
    stations = db.query(Station).all()
    predictions: List[MaintenancePredictionResponse] = []
    now = datetime.now(timezone.utc)

    for st in stations:
        features = extract_station_health_features(db, st)
        p_fail, risk_lvl, top_drv, rec_action, factors = calculate_failure_risk(features)

        # Persist prediction
        row = MaintenancePrediction(
            station_id=st.id,
            predicted_at=now,
            failure_probability_30d=p_fail,
            top_factors=factors,
        )
        db.add(row)
        db.flush()

        predictions.append(
            MaintenancePredictionResponse(
                id=row.id,
                station_id=str(st.id),
                station_code=st.station_code,
                station_name=st.name,
                state=st.state,
                district=st.district,
                status=st.status.value if hasattr(st.status, "value") else str(st.status),
                predicted_at=now,
                failure_probability_30d=p_fail,
                risk_level=risk_lvl,
                top_driver=top_drv,
                recommended_action=rec_action,
                top_factors=factors,
            )
        )

    db.commit()

    # Sort descending by failure probability (highest risk first)
    predictions.sort(key=lambda p: p.failure_probability_30d, reverse=True)
    return predictions


def get_ranked_predictions(
    db: Session,
    risk_level: Optional[str] = None,
) -> FleetMaintenanceSummary:
    """
    Retrieve current fleet-wide failure risk rankings.
    If no predictions exist, automatically computes them.
    """
    count = db.query(func.count(MaintenancePrediction.id)).scalar() or 0
    if count == 0:
        recompute_fleet_predictions(db)

    # Fetch latest prediction per station
    stations = db.query(Station).all()
    predictions: List[MaintenancePredictionResponse] = []

    for st in stations:
        latest = (
            db.query(MaintenancePrediction)
            .filter(MaintenancePrediction.station_id == st.id)
            .order_by(desc(MaintenancePrediction.predicted_at))
            .first()
        )
        if not latest:
            continue

        factors = latest.top_factors or {}
        risk_lvl = factors.get("risk_level", "nominal")
        top_drv = factors.get("top_driver", "Nominal Baseline")
        rec_action = factors.get("recommended_action", "Routine monitoring")

        predictions.append(
            MaintenancePredictionResponse(
                id=latest.id,
                station_id=str(st.id),
                station_code=st.station_code,
                station_name=st.name,
                state=st.state,
                district=st.district,
                status=st.status.value if hasattr(st.status, "value") else str(st.status),
                predicted_at=latest.predicted_at,
                failure_probability_30d=latest.failure_probability_30d,
                risk_level=risk_lvl,
                top_driver=top_drv,
                recommended_action=rec_action,
                top_factors=factors,
            )
        )

    # Sort descending by failure probability
    predictions.sort(key=lambda p: p.failure_probability_30d, reverse=True)

    # Calculate summary metrics across all stations before filtering
    total_st = len(predictions)
    crit_count = sum(1 for p in predictions if p.risk_level == "critical")
    elev_count = sum(1 for p in predictions if p.risk_level == "elevated")
    mod_count = sum(1 for p in predictions if p.risk_level == "moderate")
    nom_count = sum(1 for p in predictions if p.risk_level == "nominal")
    mean_prob = round(sum(p.failure_probability_30d for p in predictions) / max(total_st, 1), 4)

    # Filter by risk level if requested
    if risk_level:
        predictions = [p for p in predictions if p.risk_level.lower() == risk_level.lower()]

    return FleetMaintenanceSummary(
        total_stations=total_st,
        critical_risk_count=crit_count,
        elevated_risk_count=elev_count,
        moderate_risk_count=mod_count,
        nominal_risk_count=nom_count,
        mean_failure_probability=mean_prob,
        ranked_predictions=predictions,
    )


def get_station_maintenance_detail(
    db: Session,
    station_id: uuid.UUID,
) -> Optional[MaintenancePredictionResponse]:
    """Retrieve detailed maintenance diagnostics for a single station."""
    st = db.query(Station).filter(Station.id == station_id).first()
    if not st:
        return None

    latest = (
        db.query(MaintenancePrediction)
        .filter(MaintenancePrediction.station_id == st.id)
        .order_by(desc(MaintenancePrediction.predicted_at))
        .first()
    )

    if not latest:
        # Compute on the fly if missing
        features = extract_station_health_features(db, st)
        p_fail, risk_lvl, top_drv, rec_action, factors = calculate_failure_risk(features)
        now = datetime.now(timezone.utc)
        latest = MaintenancePrediction(
            station_id=st.id,
            predicted_at=now,
            failure_probability_30d=p_fail,
            top_factors=factors,
        )
        db.add(latest)
        db.commit()
        db.refresh(latest)

    factors = latest.top_factors or {}
    return MaintenancePredictionResponse(
        id=latest.id,
        station_id=str(st.id),
        station_code=st.station_code,
        station_name=st.name,
        state=st.state,
        district=st.district,
        status=st.status.value if hasattr(st.status, "value") else str(st.status),
        predicted_at=latest.predicted_at,
        failure_probability_30d=latest.failure_probability_30d,
        risk_level=factors.get("risk_level", "nominal"),
        top_driver=factors.get("top_driver", "Nominal Baseline"),
        recommended_action=factors.get("recommended_action", "Routine monitoring"),
        top_factors=factors,
    )
