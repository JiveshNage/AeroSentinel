"""
routes.py — Alerts API Endpoints (F10)
"""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from storage.db import get_db
from storage.models import Alert, AlertSeverity, AlertStatus, Station, QCResult
from alerts.schemas import AlertResponse, AlertListResponse, UpdateAlertRequest
from alerts.service import ws_manager, update_alert_status


router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertListResponse)
def list_alerts(
    status_filter: Optional[AlertStatus] = Query(None, alias="status", description="Filter by alert status"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by alert severity"),
    station_id: Optional[str] = Query(None, description="Filter by station UUID or station_code"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List operational alerts with filtering and pagination."""
    query = (
        db.query(Alert, Station.station_code, Station.name, QCResult.variable)
        .join(Station, Alert.station_id == Station.id)
        .join(QCResult, Alert.qc_result_id == QCResult.id)
    )

    if status_filter:
        query = query.filter(Alert.status == status_filter)

    if severity:
        query = query.filter(Alert.severity == severity)

    if station_id:
        try:
            val_uuid = uuid.UUID(station_id)
            query = query.filter(Alert.station_id == val_uuid)
        except ValueError:
            query = query.filter(Station.station_code == station_id)

    total = query.count()
    rows = query.order_by(desc(Alert.created_at)).offset(offset).limit(limit).all()

    alert_responses = []
    for alert_obj, st_code, st_name, var_name in rows:
        resp = AlertResponse(
            id=alert_obj.id,
            station_id=alert_obj.station_id,
            station_code=st_code,
            station_name=st_name,
            qc_result_id=alert_obj.qc_result_id,
            variable=var_name,
            severity=alert_obj.severity,
            status=alert_obj.status,
            message=alert_obj.message,
            channel_sent=alert_obj.channel_sent or {},
            created_at=alert_obj.created_at,
            resolved_at=alert_obj.resolved_at,
        )
        alert_responses.append(resp)

    return AlertListResponse(total=total, alerts=alert_responses)


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    """Retrieve full details of a specific alert."""
    row = (
        db.query(Alert, Station.station_code, Station.name, QCResult.variable)
        .join(Station, Alert.station_id == Station.id)
        .join(QCResult, Alert.qc_result_id == QCResult.id)
        .filter(Alert.id == alert_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found.")

    alert_obj, st_code, st_name, var_name = row
    return AlertResponse(
        id=alert_obj.id,
        station_id=alert_obj.station_id,
        station_code=st_code,
        station_name=st_name,
        qc_result_id=alert_obj.qc_result_id,
        variable=var_name,
        severity=alert_obj.severity,
        status=alert_obj.status,
        message=alert_obj.message,
        channel_sent=alert_obj.channel_sent or {},
        created_at=alert_obj.created_at,
        resolved_at=alert_obj.resolved_at,
    )


@router.patch("/{alert_id}", response_model=AlertResponse)
def update_alert(
    alert_id: int,
    request: UpdateAlertRequest,
    db: Session = Depends(get_db),
):
    """Acknowledge or resolve an active alert."""
    updated = update_alert_status(db, alert_id=alert_id, new_status=request.status)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found.")

    return get_alert(alert_id, db=db)


@router.websocket("/ws")
async def websocket_alerts_endpoint(websocket: WebSocket):
    """Live WebSocket stream for real-time alert broadcasts."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; accept incoming pings from client
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
