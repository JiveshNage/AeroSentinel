"""
service.py — Alerts Service (F10)
Feature: F10 — Alerts service (Phase 3)

1. Maps verdict + confidence + reason_code to AlertSeverity (low, medium, high, critical).
2. Generates human-readable, domain-specific alert summaries.
3. Implements alert deduplication / debouncing within cooldown windows to avoid alert fatigue.
4. Manages WebSocket connections and broadcasts real-time alert events to active dashboard clients.
5. Sends notification stubs (email/SMS).
"""

import asyncio
from datetime import datetime, timezone, timedelta
import json
import logging
from typing import List, Optional, Tuple, Dict, Any
import uuid

from fastapi import WebSocket
from sqlalchemy.orm import Session
from sqlalchemy import desc

from storage.models import Station, RawReading, QCResult, QCVerdict, Alert, AlertSeverity, AlertStatus


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections for live real-time alert broadcasting."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total active: {len(self.active_connections)}")

    async def broadcast_json(self, message: Dict[str, Any]):
        """Broadcast JSON message to all connected clients asynchronously."""
        if not self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket client: {e}")
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)


# Global WebSocket connection manager instance
ws_manager = ConnectionManager()


def determine_severity(
    verdict: QCVerdict,
    confidence: float,
    reason_code: str,
    fault_type: Optional[str] = None,
    variable: str = "temperature",
) -> Optional[AlertSeverity]:
    """
    Rule mapping: verdict + confidence + reason_code -> AlertSeverity.
    Returns None if reading is valid or non-actionable.
    """
    if verdict == QCVerdict.valid:
        return None

    # Suspect readings without severe fault
    if verdict == QCVerdict.suspect:
        return AlertSeverity.low

    # Anomalous verdicts:
    # 1. Critical: extreme physical range violations or severe spatial divergence
    if reason_code == "RULE_RANGE":
        return AlertSeverity.critical

    if reason_code == "SPATIAL_MISMATCH" and confidence >= 0.95:
        return AlertSeverity.critical

    # 2. High: verified physical faults (flatline, step jump, confirmed ML + spatial drift)
    if reason_code in ("RULE_FLATLINE", "RULE_STEP", "ML_AND_SPATIAL_CONFIRMED", "SPATIAL_MISMATCH"):
        return AlertSeverity.high

    # 3. Medium: single-model ML anomaly with moderate confidence
    if reason_code == "ML_ISOFOREST":
        return AlertSeverity.medium if confidence >= 0.70 else AlertSeverity.low

    return AlertSeverity.medium


def format_alert_message(
    station_code: str,
    station_name: str,
    variable: str,
    severity: AlertSeverity,
    reason_code: str,
    fault_type: Optional[str],
    confidence: float,
    details: Dict[str, Any],
) -> str:
    """Format human-readable, domain-specific alert notification message."""
    conf_pct = int(round(confidence * 100))
    prefix = f"[{severity.value.upper()}] {station_name} ({station_code}) - {variable.capitalize()}: "

    if reason_code == "RULE_RANGE":
        val = details.get("rule", {}).get("details", {}).get("value")
        return f"{prefix}Sensor value {val} breached physical bounds (Confidence: {conf_pct}%)."

    if reason_code == "RULE_FLATLINE":
        count = details.get("rule", {}).get("details", {}).get("consecutive_count", 6)
        val = details.get("rule", {}).get("details", {}).get("identical_value")
        return f"{prefix}Sensor stuck / persistent flatline detected ({count} identical readings at {val})."

    if reason_code == "RULE_STEP":
        delta = details.get("rule", {}).get("details", {}).get("delta")
        return f"{prefix}Sudden implausible rate-of-change jump (+{delta}) without regional confirmation."

    if reason_code == "ML_AND_SPATIAL_CONFIRMED":
        return f"{prefix}Calibration drift confirmed by both ML reconstruction error and neighboring AWS deviation (Confidence: {conf_pct}%)."

    if reason_code == "SPATIAL_MISMATCH":
        z = details.get("spatial", {}).get("details", {}).get("z_score")
        delta = details.get("spatial", {}).get("details", {}).get("spatial_delta")
        return f"{prefix}Spatial mismatch with neighboring stations (delta: {delta}, z-score: {z})."

    if reason_code == "ML_ISOFOREST":
        score = details.get("ml", {}).get("score", 0.0)
        return f"{prefix}Statistical anomaly flagged by Isolation Forest (anomaly score: {score})."

    return f"{prefix}Anomalous sensor behavior detected ({reason_code}, Confidence: {conf_pct}%)."


def create_alert_for_qc_result(
    db: Session,
    qc_result: QCResult,
    cooldown_minutes: int = 60,
) -> Optional[Alert]:
    """
    Creates an operational alert for an anomalous QCResult.
    Deduplicates repeating alerts for the same station and variable within cooldown_minutes.
    Dispatches to WebSocket subscribers and logs notification stubs.
    """
    severity = determine_severity(
        verdict=qc_result.verdict,
        confidence=qc_result.confidence,
        reason_code=qc_result.reason_code,
        fault_type=qc_result.fault_type,
        variable=qc_result.variable,
    )
    if not severity:
        return None

    station = db.query(Station).filter(Station.id == qc_result.station_id).first()
    if not station:
        return None

    # Check for existing open alert within cooldown window
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
    existing_alert = (
        db.query(Alert)
        .join(QCResult, Alert.qc_result_id == QCResult.id)
        .filter(
            Alert.station_id == station.id,
            Alert.status == AlertStatus.open,
            QCResult.variable == qc_result.variable,
            Alert.created_at >= cutoff,
        )
        .first()
    )

    if existing_alert:
        # Debounce: update existing open alert with newest reading reference
        existing_alert.qc_result_id = qc_result.id
        if severity.value in ("critical", "high") and existing_alert.severity.value not in ("critical", "high"):
            existing_alert.severity = severity
        db.commit()
        db.refresh(existing_alert)
        return existing_alert

    # Format human-readable notification
    msg = format_alert_message(
        station_code=station.station_code,
        station_name=station.name,
        variable=qc_result.variable,
        severity=severity,
        reason_code=qc_result.reason_code,
        fault_type=qc_result.fault_type,
        confidence=qc_result.confidence,
        details=qc_result.details or {},
    )

    channel_payload = {
        "websocket": True,
        "email_stub": {
            "recipient": "duty_officer@imd.gov.in",
            "subject": f"AeroSentinel Alert: {station.station_code} - {severity.value.upper()}",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    alert = Alert(
        station_id=station.id,
        qc_result_id=qc_result.id,
        severity=severity,
        status=AlertStatus.open,
        message=msg,
        channel_sent=channel_payload,
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Asynchronously broadcast to WebSocket clients
    broadcast_data = {
        "event": "new_alert",
        "alert": {
            "id": alert.id,
            "station_id": str(alert.station_id),
            "station_code": station.station_code,
            "station_name": station.name,
            "variable": qc_result.variable,
            "severity": alert.severity.value,
            "status": alert.status.value,
            "message": alert.message,
            "created_at": alert.created_at.isoformat(),
        },
    }

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            asyncio.create_task(ws_manager.broadcast_json(broadcast_data))
        else:
            asyncio.run(ws_manager.broadcast_json(broadcast_data))
    except Exception:
        pass

    return alert


def update_alert_status(
    db: Session,
    alert_id: int,
    new_status: AlertStatus,
) -> Optional[Alert]:
    """Acknowledge or resolve an operational alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return None

    alert.status = new_status
    if new_status == AlertStatus.resolved:
        alert.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)
    return alert
