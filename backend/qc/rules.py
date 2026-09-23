"""
rules.py — Pure Rule-Based Quality Control Layer for Automatic Weather Stations
Feature: F4 — Rule-based QC layer (Phase 2)

Performs deterministic first-pass sanity checks against:
1. Range Check: validates sensor values within physical [min, max] limits from station.sensor_specs.
2. Step Check: validates rate-of-change between consecutive observations (with circular difference for wind direction).
3. Persistence / Flatline Check: detects sensor freeze (consecutive identical values), with meteorological
   exceptions for physically valid zeros (dry weather rainfall and nighttime solar radiation).
4. Full Reading Pipeline: evaluates all sensor variables and persists verdicts to qc_results table.
"""

from datetime import datetime, timezone
import math
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import desc

from storage.models import Station, RawReading, QCResult, QCVerdict


DEFAULT_SENSOR_SPECS: Dict[str, Dict[str, Any]] = {
    "temperature": {"min": -10.0, "max": 55.0, "step_max": 8.0, "persistence_max": 6, "unit": "°C"},
    "humidity": {"min": 0.0, "max": 100.0, "step_max": 30.0, "persistence_max": 6, "unit": "%"},
    "pressure": {"min": 850.0, "max": 1080.0, "step_max": 15.0, "persistence_max": 6, "unit": "hPa"},
    "wind_speed": {"min": 0.0, "max": 65.0, "step_max": 20.0, "persistence_max": 6, "unit": "m/s"},
    "wind_direction": {"min": 0.0, "max": 360.0, "step_max": 180.0, "persistence_max": 6, "unit": "degrees"},
    "rainfall": {"min": 0.0, "max": 300.0, "step_max": 100.0, "persistence_max": 6, "unit": "mm"},
    "solar_radiation": {"min": 0.0, "max": 1500.0, "step_max": 500.0, "persistence_max": 6, "unit": "W/m²"},
}

MONITORED_VARIABLES: List[str] = [
    "temperature",
    "humidity",
    "pressure",
    "wind_speed",
    "wind_direction",
    "rainfall",
    "solar_radiation",
]


def check_range(
    value: Optional[float],
    min_val: float,
    max_val: float,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Pure function: Range check against physical limits.
    Returns (is_valid, reason_code, details).
    None values do not violate range checks (handled separately by missing-data / dropout checks).
    """
    if value is None:
        return True, None, None

    if math.isnan(value) or math.isinf(value):
        return False, "RULE_RANGE_FAIL", {
            "value": "NaN" if math.isnan(value) else "Inf",
            "min": min_val,
            "max": max_val,
            "violation": "non_finite_number",
        }

    if value < min_val:
        return False, "RULE_RANGE_FAIL", {
            "value": round(float(value), 3),
            "min": min_val,
            "max": max_val,
            "violation": "below_min",
        }

    if value > max_val:
        return False, "RULE_RANGE_FAIL", {
            "value": round(float(value), 3),
            "min": min_val,
            "max": max_val,
            "violation": "above_max",
        }

    return True, None, None


def check_step(
    current_value: Optional[float],
    previous_value: Optional[float],
    max_step: float,
    is_circular: bool = False,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Pure function: Step check for implausible jumps between consecutive readings.
    For circular variables (wind direction 0-360°), uses circular minimal angular difference.
    """
    if current_value is None or previous_value is None:
        return True, None, None

    if math.isnan(current_value) or math.isnan(previous_value):
        return True, None, None

    if is_circular:
        # Minimal difference on a 360° circle
        raw_diff = abs(current_value - previous_value) % 360.0
        delta = min(raw_diff, 360.0 - raw_diff)
    else:
        delta = abs(current_value - previous_value)

    if delta > max_step:
        return False, "RULE_STEP_FAIL", {
            "current": round(float(current_value), 3),
            "previous": round(float(previous_value), 3),
            "delta": round(float(delta), 3),
            "max_step": max_step,
            "is_circular": is_circular,
        }

    return True, None, None


def check_persistence(
    values: List[Optional[float]],
    max_identical: int = 6,
    variable: str = "temperature",
    timestamp: Optional[datetime] = None,
    tolerance: float = 1e-5,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Pure function: Persistence / flatline check.
    Detects frozen sensors where the last `max_identical` consecutive values are identical.

    Domain-specific meteorological exemptions:
    1. Rainfall: 0.0 mm is normal dry weather, NOT a frozen sensor.
    2. Solar radiation: 0.0 W/m² at night (or 0.0 values) is physically valid nighttime, NOT a frozen sensor.
    """
    if len(values) < max_identical:
        return True, None, None

    recent_window = values[-max_identical:]

    # If any value in window is None or NaN, cannot definitively assert identical freeze
    for v in recent_window:
        if v is None or math.isnan(v):
            return True, None, None

    first_val = recent_window[0]

    # Check meteorological physical exemptions
    if variable == "rainfall" and abs(first_val - 0.0) < tolerance:
        # All zeros for rainfall in dry season is expected normal weather
        if all(abs(v - 0.0) < tolerance for v in recent_window):
            return True, None, None

    if variable == "solar_radiation" and abs(first_val - 0.0) < tolerance:
        # All zeros for solar radiation at night is physically valid
        if all(abs(v - 0.0) < tolerance for v in recent_window):
            return True, None, None

    # Check if all values in the window are identical within tolerance
    if all(abs(v - first_val) < tolerance for v in recent_window):
        return False, "RULE_PERSISTENCE_FAIL", {
            "identical_value": round(float(first_val), 3),
            "consecutive_count": max_identical,
            "max_identical_allowed": max_identical,
            "variable": variable,
        }

    return True, None, None


def evaluate_reading_rules(
    reading: RawReading,
    station: Station,
    recent_readings: Optional[List[RawReading]] = None,
) -> List[QCResult]:
    """
    Evaluate all pure QC rules for a given reading against station metadata and prior readings.
    Returns a list of QCResult records (one per monitored variable).
    """
    specs = station.sensor_specs or {}
    results: List[QCResult] = []

    # Sort recent readings chronologically
    sorted_recent = sorted(recent_readings, key=lambda r: r.timestamp) if recent_readings else []

    # Pre-extract prior reading for step check
    prev_reading = sorted_recent[-1] if sorted_recent else None

    for var_name in MONITORED_VARIABLES:
        val = getattr(reading, var_name, None)

        # Get variable specs with fallback defaults
        var_spec = specs.get(var_name, DEFAULT_SENSOR_SPECS.get(var_name, {}))
        min_val = var_spec.get("min", -9999.0)
        max_val = var_spec.get("max", 9999.0)
        step_max = var_spec.get("step_max", 9999.0)
        persistence_max = var_spec.get("persistence_max", 6)
        is_circular = (var_name == "wind_direction")

        # 1. Range Check
        r_valid, r_code, r_details = check_range(val, min_val, max_val)
        if not r_valid:
            results.append(
                QCResult(
                    reading_id=reading.id,
                    station_id=station.id,
                    variable=var_name,
                    verdict=QCVerdict.anomalous,
                    reason_code=r_code,
                    fault_type="spike",
                    confidence=0.98,
                    details=r_details or {},
                )
            )
            continue

        # 2. Step Check
        prev_val = getattr(prev_reading, var_name, None) if prev_reading else None
        s_valid, s_code, s_details = check_step(val, prev_val, step_max, is_circular=is_circular)
        if not s_valid:
            results.append(
                QCResult(
                    reading_id=reading.id,
                    station_id=station.id,
                    variable=var_name,
                    verdict=QCVerdict.anomalous,
                    reason_code=s_code,
                    fault_type="spike",
                    confidence=0.95,
                    details=s_details or {},
                )
            )
            continue

        # 3. Persistence Check
        # Build consecutive values sequence ending with current reading
        history_values = [getattr(r, var_name, None) for r in sorted_recent]
        history_values.append(val)
        p_valid, p_code, p_details = check_persistence(
            values=history_values,
            max_identical=persistence_max,
            variable=var_name,
            timestamp=reading.timestamp,
        )
        if not p_valid:
            results.append(
                QCResult(
                    reading_id=reading.id,
                    station_id=station.id,
                    variable=var_name,
                    verdict=QCVerdict.anomalous,
                    reason_code=p_code,
                    fault_type="flatline",
                    confidence=0.95,
                    details=p_details or {},
                )
            )
            continue

        # All rules passed for this variable
        results.append(
            QCResult(
                reading_id=reading.id,
                station_id=station.id,
                variable=var_name,
                verdict=QCVerdict.valid,
                reason_code="VALID_READING",
                fault_type=None,
                confidence=1.0,
                details={"status": "passed_all_rules", "value": val},
            )
        )

    return results


def run_qc_rules_for_reading(db: Session, reading_id: int) -> List[QCResult]:
    """
    Database service function:
    1. Fetches RawReading and associated Station.
    2. Fetches recent prior readings for persistence / step windows.
    3. Evaluates QC rules.
    4. Persists QCResult records inside an atomic transaction.
    """
    reading = db.query(RawReading).filter(RawReading.id == reading_id).first()
    if not reading:
        raise ValueError(f"RawReading with id {reading_id} not found.")

    station = db.query(Station).filter(Station.id == reading.station_id).first()
    if not station:
        raise ValueError(f"Station with id {reading.station_id} not found for reading {reading_id}.")

    # Fetch up to 20 prior readings strictly before current timestamp
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
    # Reverse so they are in chronological ascending order
    prior_readings = list(reversed(prior_readings))

    qc_results = evaluate_reading_rules(
        reading=reading,
        station=station,
        recent_readings=prior_readings,
    )

    # Persist in transaction
    try:
        for qcr in qc_results:
            db.add(qcr)
        db.commit()
        for qcr in qc_results:
            db.refresh(qcr)
        return qc_results
    except Exception:
        db.rollback()
        raise
