"""
schemas.py — Pydantic schemas for Model Retraining Service (F14)
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class RetrainRequest(BaseModel):
    variable: str = Field(default="temperature", description="Sensor variable to retrain model for")
    new_version: Optional[str] = Field(default=None, description="Custom semver or version string")
    target_false_alarm_reduction: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Target ratio of operator-marked false alarms to eliminate"
    )


class RetrainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    variable: str
    previous_version: Optional[str] = None
    new_version: str
    model_registry_id: int
    metrics: Dict[str, Any]
    artifact_path: str
    trained_at: datetime
    message: str


class ModelRegistryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_type: str
    variable: str
    version: str
    trained_at: datetime
    training_data_range: Optional[str] = None
    metrics: Dict[str, Any] = {}
    artifact_path: str
    is_active: bool


class ModelRegistryListResponse(BaseModel):
    total: int
    models: List[ModelRegistryResponse]


class FeedbackPoolStatsResponse(BaseModel):
    variable: str
    total_feedback_count: int
    confirmed_faults_count: int
    false_alarms_count: int
    unsure_count: int
    can_retrain: bool
    active_model_version: Optional[str] = None
