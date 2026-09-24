"""
routes.py — REST API Endpoints for Feature F16 Predictive Maintenance
"""

from typing import Optional, List
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from storage.db import get_db
from maintenance.schemas import (
    MaintenancePredictionResponse,
    FleetMaintenanceSummary,
)
from maintenance.service import (
    get_ranked_predictions,
    recompute_fleet_predictions,
    get_station_maintenance_detail,
)

router = APIRouter(prefix="/maintenance", tags=["Predictive Maintenance"])


@router.get("/predictions", response_model=FleetMaintenanceSummary)
def list_maintenance_predictions(
    risk_level: Optional[str] = Query(None, description="Filter by risk category: critical | elevated | moderate | nominal"),
    db: Session = Depends(get_db),
):
    """
    Retrieve fleet-wide ranked failure-risk list predicting probability of failure
    in the next 30 days, sorted highest to lowest risk.
    """
    return get_ranked_predictions(db, risk_level=risk_level)


@router.post("/recompute", response_model=FleetMaintenanceSummary)
def trigger_fleet_recompute(
    db: Session = Depends(get_db),
):
    """
    Recompute failure probability scores across all registered AWS stations
    based on the latest telemetry, QC verdicts, and alert history.
    """
    recompute_fleet_predictions(db)
    return get_ranked_predictions(db)


@router.get("/stations/{station_id}", response_model=MaintenancePredictionResponse)
def get_station_prediction(
    station_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve detailed 30-day failure risk diagnosis, top contributing factors,
    and recommended field technician actions for a specific station.
    """
    try:
        st_uuid = uuid.UUID(station_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid station UUID format")

    detail = get_station_maintenance_detail(db, st_uuid)
    if not detail:
        raise HTTPException(status_code=404, detail="Station not found")
    return detail
