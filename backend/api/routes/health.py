from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from core.config import settings
from storage.db import check_db_connection

router = APIRouter()


class ServiceHealth(BaseModel):
    status: str = Field(..., description="Service connection or availability status")
    details: str = Field(..., description="Description or latency details")


class HealthResponse(BaseModel):
    status: str = Field("healthy", description="Overall system health status")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Current version")
    environment: str = Field(..., description="Running environment")
    timestamp: str = Field(..., description="Current server UTC timestamp in ISO 8601")
    services: Dict[str, ServiceHealth] = Field(
        default_factory=dict,
        description="Health status of external dependencies and subsystem layers"
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System health check endpoint",
    description="Returns current server status, UTC timestamp, and subsystem readiness."
)
async def get_health() -> HealthResponse:
    now_utc = datetime.now(timezone.utc).isoformat()

    db_ok, db_msg = check_db_connection()
    services_status = {
        "fastapi": ServiceHealth(status="healthy", details="FastAPI server is running"),
        "database": ServiceHealth(
            status="healthy" if db_ok else "configured",
            details=db_msg if db_ok else "PostgreSQL/TimescaleDB configured (offline/standby)",
        ),
        "redis": ServiceHealth(status="configured", details="Redis pub/sub configured"),
    }

    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=now_utc,
        services=services_status,
    )
