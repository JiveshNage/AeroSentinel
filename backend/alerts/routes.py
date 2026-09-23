"""
routes.py — Alerts API Endpoints (F10)
"""

from datetime import datetime, timezone
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from storage.db import get_db
from storage.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Station,
    QCResult,
    Feedback,
    FeedbackLabel,
    User,
    UserRole,
)
from alerts.schemas import (
    AlertResponse,
    AlertListResponse,
    UpdateAlertRequest,
    SubmitFeedbackRequest,
    FeedbackResponse,
    FeedbackListResponse,
)
from alerts.service import ws_manager, update_alert_status


router = APIRouter(prefix="/alerts", tags=["alerts"])
feedback_router = APIRouter(prefix="/feedback", tags=["feedback"])


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

    qc_result_ids = [r[0].qc_result_id for r in rows]
    feedback_map = {}
    if qc_result_ids:
        fb_rows = (
            db.query(Feedback.qc_result_id, Feedback.label)
            .filter(Feedback.qc_result_id.in_(qc_result_ids))
            .order_by(desc(Feedback.created_at))
            .all()
        )
        for q_id, f_label in fb_rows:
            if q_id not in feedback_map:
                feedback_map[q_id] = f_label.value if hasattr(f_label, "value") else str(f_label)

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
            feedback_label=feedback_map.get(alert_obj.qc_result_id),
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
    fb = (
        db.query(Feedback.label)
        .filter(Feedback.qc_result_id == alert_obj.qc_result_id)
        .order_by(desc(Feedback.created_at))
        .first()
    )
    fb_label = None
    if fb:
        fb_label = fb[0].value if hasattr(fb[0], "value") else str(fb[0])

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
        feedback_label=fb_label,
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


@router.post("/{alert_id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    alert_id: int,
    request: SubmitFeedbackRequest,
    db: Session = Depends(get_db),
):
    """Operator ground-truth feedback capture on an alert."""
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

    try:
        label_enum = FeedbackLabel(request.label)
    except ValueError:
        valid_labels = [e.value for e in FeedbackLabel]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid feedback label '{request.label}'. Must be one of {valid_labels}."
        )

    user = None
    if request.user_email:
        user = db.query(User).filter(User.email == request.user_email).first()
        if not user:
            name_part = request.user_email.split("@")[0].replace(".", " ").capitalize()
            user = User(
                name=name_part,
                email=request.user_email,
                role=UserRole.data_quality_officer,
                password_hash="placeholder_hash"
            )
            db.add(user)
            db.flush()

    feedback = Feedback(
        qc_result_id=alert_obj.qc_result_id,
        user_id=user.id if user else None,
        label=label_enum,
        notes=request.notes,
        created_at=datetime.now(timezone.utc),
    )
    db.add(feedback)

    # Automatically transition alert lifecycle based on feedback
    if label_enum == FeedbackLabel.confirmed_fault:
        if alert_obj.status == AlertStatus.open:
            alert_obj.status = AlertStatus.acknowledged
    elif label_enum == FeedbackLabel.false_alarm:
        alert_obj.status = AlertStatus.resolved
        alert_obj.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(feedback)

    return FeedbackResponse(
        id=feedback.id,
        alert_id=alert_obj.id,
        qc_result_id=feedback.qc_result_id,
        station_code=st_code,
        station_name=st_name,
        variable=var_name,
        label=feedback.label.value if hasattr(feedback.label, "value") else str(feedback.label),
        notes=feedback.notes,
        user_id=feedback.user_id,
        user_email=user.email if user else None,
        created_at=feedback.created_at,
    )


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


@feedback_router.get("", response_model=FeedbackListResponse)
def list_feedback(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    label: Optional[str] = Query(None, description="Filter by feedback label"),
    db: Session = Depends(get_db),
):
    """List historical operator feedback for model retraining audits."""
    query = (
        db.query(Feedback, Station.station_code, Station.name, QCResult.variable, User.email)
        .join(QCResult, Feedback.qc_result_id == QCResult.id)
        .join(Station, QCResult.station_id == Station.id)
        .outerjoin(User, Feedback.user_id == User.id)
    )

    if label:
        try:
            label_enum = FeedbackLabel(label)
            query = query.filter(Feedback.label == label_enum)
        except ValueError:
            valid_labels = [e.value for e in FeedbackLabel]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid feedback label '{label}'. Must be one of {valid_labels}."
            )

    total = query.count()
    rows = query.order_by(desc(Feedback.created_at)).offset(offset).limit(limit).all()

    qc_result_ids = [r[0].qc_result_id for r in rows]
    alert_map = {}
    if qc_result_ids:
        alert_rows = db.query(Alert.id, Alert.qc_result_id).filter(Alert.qc_result_id.in_(qc_result_ids)).all()
        for a_id, q_id in alert_rows:
            alert_map[q_id] = a_id

    feedbacks = []
    for fb, st_code, st_name, var_name, u_email in rows:
        feedbacks.append(
            FeedbackResponse(
                id=fb.id,
                alert_id=alert_map.get(fb.qc_result_id),
                qc_result_id=fb.qc_result_id,
                station_code=st_code,
                station_name=st_name,
                variable=var_name,
                label=fb.label.value if hasattr(fb.label, "value") else str(fb.label),
                notes=fb.notes,
                user_id=fb.user_id,
                user_email=u_email,
                created_at=fb.created_at,
            )
        )

    return FeedbackListResponse(total=total, feedback=feedbacks)
