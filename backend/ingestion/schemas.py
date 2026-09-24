from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class IngestReadingRequest(BaseModel):
    station_id: str = Field(..., description="IMD station code (e.g. 'NCR001') or station UUID")
    timestamp: datetime = Field(..., description="Reading measurement timestamp in ISO 8601")
    temperature: Optional[float] = Field(None, description="Air temperature in °C")
    humidity: Optional[float] = Field(None, description="Relative humidity in %")
    pressure: Optional[float] = Field(None, description="Atmospheric pressure in hPa")
    wind_speed: Optional[float] = Field(None, description="Wind speed in m/s")
    wind_direction: Optional[float] = Field(None, description="Wind direction in degrees (0-360)")
    rainfall: Optional[float] = Field(None, description="Rainfall accumulation in mm")
    solar_radiation: Optional[float] = Field(None, description="Solar radiation in W/m²")
    ingest_source: str = Field("simulator", description="Source identifier: 'simulator', 'live', 'meteostat_historical'")

    @field_validator("timestamp")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        """Ensure naive datetimes are localized to UTC consistently."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_validator("humidity")
    @classmethod
    def validate_humidity_bounds(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0.0 or v > 100.0):
            # Physical bounds check on ingestion: humidity cannot be negative or > 100%
            raise ValueError(f"Humidity must be between 0% and 100%, got {v}")
        return v

    @field_validator("wind_direction")
    @classmethod
    def validate_wind_direction_bounds(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0.0 or v > 360.0):
            raise ValueError(f"Wind direction must be between 0 and 360 degrees, got {v}")
        return v


class BatchIngestRequest(BaseModel):
    readings: List[IngestReadingRequest] = Field(..., min_length=1, max_length=1000)


class IngestResponse(BaseModel):
    status: str = Field("ingested", description="Ingestion status")
    reading_id: int = Field(..., description="ID of persisted raw_reading record")
    station_code: str = Field(..., description="Station IMD code")
    station_id: str = Field(..., description="Internal station UUID")
    timestamp: datetime = Field(..., description="Measurement timestamp (UTC)")


class BatchIngestResponse(BaseModel):
    status: str = Field("completed", description="Batch ingestion status")
    total_received: int = Field(..., description="Count of readings received in batch")
    ingested: int = Field(..., description="Count of newly persisted readings")
    duplicates_skipped: int = Field(..., description="Count of duplicate readings skipped")
    reading_ids: List[int] = Field(default_factory=list, description="IDs of newly inserted readings")


class FileRowPreview(BaseModel):
    station_code: str
    timestamp: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    rainfall: Optional[float] = None
    qc_verdict: Optional[str] = "valid"
    fault_type: Optional[str] = None


class FileUploadResponse(BaseModel):
    status: str
    filename: str
    total_rows: int
    ingested_count: int
    duplicates_skipped: int
    anomalies_detected: int
    stations_affected: List[str] = []
    preview: List[FileRowPreview] = []
    message: str

