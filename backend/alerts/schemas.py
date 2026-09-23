"""
schemas.py — Pydantic schemas for Alerts Service (F10)
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid
from pydantic import BaseModel, ConfigDict

from storage.models import AlertSeverity, AlertStatus


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    station_id: uuid.UUID
    station_code: Optional[str] = None
    station_name: Optional[str] = None
    qc_result_id: int
    variable: Optional[str] = None
    severity: AlertSeverity
    status: AlertStatus
    message: str
    channel_sent: Dict[str, Any] = {}
    created_at: datetime
    resolved_at: Optional[datetime] = None
    feedback_label: Optional[str] = None


class UpdateAlertRequest(BaseModel):
    status: AlertStatus  # acknowledged or resolved


class AlertListResponse(BaseModel):
    total: int
    alerts: List[AlertResponse]


class SubmitFeedbackRequest(BaseModel):
    label: str  # confirmed_fault, false_alarm, unsure
    notes: Optional[str] = None
    user_email: Optional[str] = None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: Optional[int] = None
    qc_result_id: int
    station_code: Optional[str] = None
    station_name: Optional[str] = None
    variable: Optional[str] = None
    label: str
    notes: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    user_email: Optional[str] = None
    created_at: datetime


class FeedbackListResponse(BaseModel):
    total: int
    feedback: List[FeedbackResponse]
