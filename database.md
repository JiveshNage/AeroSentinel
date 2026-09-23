# database.md — AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control

Engine: **PostgreSQL 15 + TimescaleDB extension** (readings table is a hypertable, partitioned by time).

## 1. `stations`
Metadata registry for every AWS station.

| Column | Type | Notes |
|---|---|---|
| id | UUID / serial PK | |
| station_code | text, unique | IMD station code |
| name | text | |
| latitude | double precision | |
| longitude | double precision | |
| elevation_m | double precision | |
| state | text | |
| district | text | |
| install_date | date | |
| sensor_specs | jsonb | per-variable valid ranges, e.g. `{"temperature": {"min": -10, "max": 55}, ...}` |
| status | enum(`active`,`maintenance`,`decommissioned`) | |
| created_at / updated_at | timestamptz | |

Index: GiST index on `(latitude, longitude)` for spatial nearest-neighbor queries (or use `earthdistance`/PostGIS if available).

## 2. `raw_readings` (Timescale hypertable, partitioned on `timestamp`)

| Column | Type | Notes |
|---|---|---|
| id | bigserial | |
| station_id | UUID FK → stations.id | |
| timestamp | timestamptz | reading time, indexed |
| temperature | real | °C |
| humidity | real | % |
| pressure | real | hPa |
| wind_speed | real | m/s |
| wind_direction | real | degrees |
| rainfall | real | mm |
| solar_radiation | real | W/m² |
| ingest_source | text | `simulator` / `live` |
| ingested_at | timestamptz | |

Unique constraint: `(station_id, timestamp)` — enforces idempotent ingestion.
Hypertable chunk interval: 1 day (tune based on ingestion volume).

## 3. `qc_results`
One row per raw reading, produced by the QC pipeline.

| Column | Type | Notes |
|---|---|---|
| id | bigserial | |
| reading_id | bigint FK → raw_readings.id | |
| station_id | UUID FK | denormalized for fast dashboard queries |
| variable | text | which sensor variable this verdict is about (readings can fail QC on a subset of variables) |
| verdict | enum(`valid`,`suspect`,`anomalous`) | |
| reason_code | text | `RULE_RANGE`, `RULE_STEP`, `RULE_FLATLINE`, `ML_RECON_ERROR`, `SPATIAL_MISMATCH`, `DROPOUT` |
| fault_type | text nullable | `spike`,`flatline`,`drift`,`dropout`,`spatial_inconsistency`,`plausible_extreme` |
| confidence | real | 0–1 |
| ml_model_version | text | which model produced the ML component of the verdict |
| details | jsonb | raw scores from each layer, for explainability in the UI |
| created_at | timestamptz | |

Index: `(station_id, created_at)`, `(verdict)`.

## 4. `alerts`

| Column | Type | Notes |
|---|---|---|
| id | bigserial | |
| station_id | UUID FK | |
| qc_result_id | bigint FK | |
| severity | enum(`low`,`medium`,`high`,`critical`) | |
| status | enum(`open`,`acknowledged`,`resolved`) | |
| message | text | human-readable summary |
| channel_sent | jsonb | which channels notified, timestamps |
| created_at / resolved_at | timestamptz | |

## 5. `feedback`
Operator labels — this is the training signal for retraining.

| Column | Type | Notes |
|---|---|---|
| id | bigserial | |
| qc_result_id | bigint FK | |
| user_id | UUID FK → users.id | |
| label | enum(`confirmed_fault`,`false_alarm`,`unsure`) | |
| notes | text | |
| created_at | timestamptz | |

## 6. `users`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | text | |
| email | text unique | |
| role | enum(`admin`,`data_quality_officer`,`forecaster`,`field_technician`) | |
| password_hash | text | |
| created_at | timestamptz | |

## 7. `model_registry`
Tracks trained model versions for auditability/rollback.

| Column | Type | Notes |
|---|---|---|
| id | bigserial | |
| model_type | text | `isolation_forest` / `lstm_autoencoder` |
| variable | text | which sensor variable it's trained for |
| version | text | semver or timestamp-based |
| trained_at | timestamptz | |
| training_data_range | tstzrange | |
| metrics | jsonb | precision/recall/AUC on holdout |
| artifact_path | text | filesystem/S3 path to serialized model |
| is_active | boolean | currently-in-production flag |

## 8. `maintenance_predictions` (stretch goal)

| Column | Type | Notes |
|---|---|---|
| id | bigserial | |
| station_id | UUID FK | |
| predicted_at | timestamptz | |
| failure_probability_30d | real | |
| top_factors | jsonb | feature importances |

## 9. Relationships (ERD summary)
```
stations 1───* raw_readings
raw_readings 1───* qc_results
qc_results 1───* alerts
qc_results 1───* feedback
users 1───* feedback
stations 1───* maintenance_predictions
model_registry (standalone, referenced by qc_results.ml_model_version)
```

## 10. Seed/demo data plan
- Load 1–2 years of historical data for ~20–50 representative Indian AWS stations (IMD open data / NOAA ISD as stand-in) into `raw_readings`.
- Build a fault-injection script that clones a clean window and mutates it (freeze value = flatline, add outlier = spike, add linear offset over time = drift, blank rows = dropout) — used both for ML training labels and for live demo.
