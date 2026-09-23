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


class UpdateAlertRequest(BaseModel):
    status: AlertStatus  # acknowledged or resolved


class AlertListResponse(BaseModel):
    total: int
    alerts: List[AlertResponse]
