# AeroSentinel API Documentation

Base URLs:
- Root: `http://localhost:8000`
- API prefix: `http://localhost:8000/api`

---

## 1. System Health

### `GET /api/health`
Returns current system operational status, UTC ISO 8601 timestamp, and diagnostic status for FastAPI, PostgreSQL/TimescaleDB, and Redis.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "app_name": "AeroSentinel",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-09-23T12:00:00.000000+00:00",
  "services": {
    "fastapi": {
      "status": "healthy",
      "details": "FastAPI server is running"
    },
    "database": {
      "status": "healthy",
      "details": "Connected (1.2ms)"
    },
    "redis": {
      "status": "configured",
      "details": "Redis pub/sub configured"
    }
  }
}
```

---

## 2. Ingestion Gateway

### `POST /ingest`
Ingests a single observation reading from an Automatic Weather Station or simulator.

**Headers:**
- `Content-Type: application/json`

**Request Body:**
```json
{
  "station_id": "NCR001",
  "timestamp": "2024-06-01T12:00:00Z",
  "temperature": 34.2,
  "humidity": 62.5,
  "pressure": 1005.4,
  "wind_speed": 4.5,
  "wind_direction": 120.0,
  "rainfall": 0.0,
  "solar_radiation": 850.0,
  "ingest_source": "simulator"
}
```

**Responses:**
- `201 Created`:
  ```json
  {
    "status": "ingested",
    "reading_id": 101,
    "station_code": "NCR001",
    "station_id": "8bbbb909-51c3-42e6-99ae-38f376cf9ca4",
    "timestamp": "2024-06-01T12:00:00Z"
  }
  ```
- `404 Not Found`: Unknown or spoofed station ID not present in registered station registry.
- `409 Conflict`: Duplicate reading on `(station_id, timestamp)`. Idempotency guarantee prevents duplicate records.
- `422 Unprocessable Entity`: Malformed payload or physical bounds failure (e.g., negative or >100% humidity, non-numeric values).

---

### `POST /ingest/batch`
Batch ingestion endpoint for historical replay or edge buffer synchronization.

**Request Body:**
```json
{
  "readings": [
    {
      "station_id": "NCR001",
      "timestamp": "2024-06-01T12:00:00Z",
      "temperature": 34.2,
      "humidity": 62.5
    },
    {
      "station_id": "NCR002",
      "timestamp": "2024-06-01T12:00:00Z",
      "temperature": 35.1,
      "humidity": 58.0
    }
  ]
}
```

**Response (201 Created):**
```json
{
  "status": "completed",
  "total_received": 2,
  "ingested": 2,
  "duplicates_skipped": 0,
  "reading_ids": [102, 103]
}
```
