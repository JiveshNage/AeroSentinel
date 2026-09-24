"""
schemas.py — Pydantic Schemas for Feature F16 Predictive Maintenance
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid


class MaintenancePredictionResponse(BaseModel):
    id: int
    station_id: str
    station_code: str
    station_name: str
    state: str
    district: str
    status: str
    predicted_at: datetime
    failure_probability_30d: float = Field(..., ge=0.0, le=1.0)
    risk_level: str  # critical | elevated | moderate | nominal
    top_driver: str
    recommended_action: str
    top_factors: Dict[str, Any]

    model_config = {"from_attributes": True}


class FleetMaintenanceSummary(BaseModel):
    total_stations: int
    critical_risk_count: int
    elevated_risk_count: int
    moderate_risk_count: int
    nominal_risk_count: int
    mean_failure_probability: float
    ranked_predictions: List[MaintenancePredictionResponse]
