"""
routes.py — REST API endpoints for Model Retraining and Governance (F14)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from storage.db import get_db
from retrain.schemas import (
    RetrainRequest,
    RetrainResponse,
    FeedbackPoolStatsResponse,
    ModelRegistryResponse,
    ModelRegistryListResponse,
)
from retrain.service import (
    get_feedback_pool_stats,
    execute_retrain_job,
    activate_model_version,
    list_registered_models,
)

router = APIRouter(prefix="/retrain", tags=["retrain"])


@router.post("/trigger", response_model=RetrainResponse, status_code=status.HTTP_200_OK)
@router.post("", response_model=RetrainResponse, status_code=status.HTTP_200_OK)
def trigger_retrain(
    request: RetrainRequest = RetrainRequest(),
    db: Session = Depends(get_db),
):
    """
    Trigger model retraining job for a specific sensor variable using operator feedback.
    Augments baseline training with false-alarm inliers, calibrates decision threshold,
    and updates active model in model_registry.
    """
    try:
        response = execute_retrain_job(
            db=db,
            variable=request.variable,
            new_version=request.new_version,
            target_false_alarm_reduction=request.target_false_alarm_reduction,
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retraining job failed: {str(e)}",
        )


@router.get("/stats", response_model=FeedbackPoolStatsResponse)
def get_stats(
    variable: str = Query("temperature", description="Sensor variable to check feedback pool for"),
    db: Session = Depends(get_db),
):
    """Inspect count of operator feedback records available for model retraining."""
    return get_feedback_pool_stats(db=db, variable=variable)


@router.get("/models", response_model=ModelRegistryListResponse)
def list_models(
    variable: Optional[str] = Query(None, description="Filter models by sensor variable"),
    db: Session = Depends(get_db),
):
    """List historical and active trained models in model_registry."""
    models = list_registered_models(db=db, variable=variable)
    return ModelRegistryListResponse(
        total=len(models),
        models=[ModelRegistryResponse.model_validate(m) for m in models],
    )


@router.post("/models/{model_id}/activate", response_model=ModelRegistryResponse)
def activate_model(
    model_id: int,
    db: Session = Depends(get_db),
):
    """
    Rollback / activate a specific model version in model_registry.
    Atomically switches is_active flag and updates inference cache.
    """
    try:
        model = activate_model_version(db=db, model_id=model_id)
        return ModelRegistryResponse.model_validate(model)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
