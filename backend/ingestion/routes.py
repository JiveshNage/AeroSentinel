from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from storage.db import get_db
from ingestion.schemas import IngestReadingRequest, BatchIngestRequest, IngestResponse, BatchIngestResponse
from ingestion.service import ingest_reading, ingest_batch, resolve_station

router = APIRouter()


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a single AWS sensor reading",
    description=(
        "Validates payload shape, resolves station against registry, checks for duplicates "
        "on (station_id, timestamp), and persists to raw_readings."
    ),
    responses={
        201: {"description": "Reading successfully validated and persisted"},
        404: {"description": "Station ID not found in registry (spoofed station rejection)"},
        409: {"description": "Duplicate reading on (station_id, timestamp)"},
        422: {"description": "Malformed payload or validation error"},
    },
)
async def post_ingest(
    payload: IngestReadingRequest,
    db: Session = Depends(get_db),
) -> IngestResponse:
    reading = ingest_reading(db, payload)
    station = resolve_station(db, payload.station_id)
    return IngestResponse(
        status="ingested",
        reading_id=reading.id,
        station_code=station.station_code,
        station_id=str(station.id),
        timestamp=reading.timestamp,
    )


@router.post(
    "/ingest/batch",
    response_model=BatchIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a batch of AWS sensor readings",
    description="Batch ingestion for simulator replay or remote station offline synchronization.",
)
async def post_ingest_batch(
    payload: BatchIngestRequest,
    db: Session = Depends(get_db),
) -> BatchIngestResponse:
    return ingest_batch(db, payload)
