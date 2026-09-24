from typing import Optional
from fastapi import APIRouter, Depends, status, UploadFile, File, Form, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from storage.db import get_db
from ingestion.schemas import (
    IngestReadingRequest,
    BatchIngestRequest,
    IngestResponse,
    BatchIngestResponse,
    FileUploadResponse,
)
from ingestion.service import ingest_reading, ingest_batch, resolve_station, process_file_upload

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


@router.post(
    "/ingest/upload-file",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest AWS observation data file (.csv, .json)",
    description=(
        "Uploads a tabular weather station data file, validates against IMD station codes, "
        "stores raw readings, and triggers the real-time ML anomaly detection pipeline."
    ),
)
async def post_upload_file(
    file: UploadFile = File(...),
    default_station_code: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    try:
        content = await file.read()
        return process_file_upload(
            db=db,
            file_bytes=content,
            filename=file.filename or "uploaded_data.csv",
            default_station_code=default_station_code,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process file upload: {str(e)}",
        )


@router.get(
    "/ingest/template.csv",
    response_class=PlainTextResponse,
    summary="Download sample CSV template for AWS data ingestion",
)
def get_sample_csv_template():
    csv_sample = (
        "station_code,timestamp,temperature,humidity,pressure,wind_speed,wind_direction,rainfall,solar_radiation\n"
        "NCR001,2026-09-24T12:00:00Z,34.2,62.0,1012.5,4.2,270,0.0,680.0\n"
        "NCR001,2026-09-24T12:15:00Z,34.5,61.5,1012.3,4.6,265,0.0,710.0\n"
        "NCR002,2026-09-24T12:00:00Z,33.8,64.2,1013.1,3.8,280,0.0,650.0\n"
        "NCR003,2026-09-24T12:00:00Z,35.1,59.8,1011.9,5.1,260,0.0,720.0\n"
    )
    return PlainTextResponse(
        content=csv_sample,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=aerosentinel_sample_template.csv"},
    )

