# architecture.md — AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control

## 1. System diagram (textual)

```
                    ┌─────────────────────────┐
                    │   AWS Station Simulator   │  (or real IMD feed later)
                    │  replays/streams readings  │
                    └────────────┬──────────────┘
                                 │ HTTP POST / MQTT
                                 ▼
                    ┌─────────────────────────┐
                    │     Ingestion Service      │  FastAPI
                    │  validates payload shape   │
                    │  writes raw reading to DB  │
                    └────────────┬──────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      QC Pipeline (core)    │
                    │  ┌───────────────────────┐ │
                    │  │ 1. Rule-based checks   │ │  range / step / persistence
                    │  ├───────────────────────┤ │
                    │  │ 2. ML anomaly scoring  │ │  IsolationForest / LSTM-AE
                    │  ├───────────────────────┤ │  reconstruction error
                    │  │ 3. Spatial consistency │ │  compare vs. k-nearest AWS
                    │  ├───────────────────────┤ │
                    │  │ 4. Fault classifier    │ │  flatline/spike/drift/
                    │  └───────────────────────┘ │  dropout/spatial-mismatch
                    └────────────┬──────────────┘
                                 │ writes QC result + reason
                                 ▼
              ┌──────────────────┴───────────────────┐
              ▼                                       ▼
   ┌─────────────────────┐                 ┌─────────────────────┐
   │   Alerts Service      │                 │   Storage (Timescale)│
   │  thresholds severity,  │◀───reads──────│  raw_readings         │
   │  pushes via WS/email    │                 │  qc_results           │
   └──────────┬───────────┘                 │  stations              │
              │                              │  alerts / feedback     │
              ▼                              └───────────┬───────────┘
   ┌─────────────────────┐                                │
   │  Notification channel │                                │
   │  (email / SMS stub)    │                                │
   └─────────────────────┘                                │
                                                            ▼
                                        ┌─────────────────────────────┐
                                        │        React Dashboard        │
                                        │  - India map (station health)  │
                                        │  - Station detail (time series)│
                                        │  - Alerts feed                 │
                                        │  - Feedback capture (confirm/ │
                                        │    reject anomaly)             │
                                        └────────────┬────────────────┘
                                                     │ feedback events
                                                     ▼
                                        ┌─────────────────────────────┐
                                        │     Retraining Job (Celery)    │
                                        │  pulls confirmed/rejected       │
                                        │  labels → retrains ML models    │
                                        │  → versions model artifact       │
                                        └─────────────────────────────┘
```

## 2. Component responsibilities

| Component | Responsibility | Talks to |
|---|---|---|
| Simulator | Emits realistic + fault-injected AWS readings | Ingestion API |
| Ingestion Service | Validates payload, persists raw reading, enqueues for QC | DB, QC Pipeline |
| Rule Engine | Fast, cheap, explainable first-pass checks | reads reading + station metadata (sensor spec ranges) |
| ML Anomaly Scorer | Statistical/deep model per variable per station | reads reading history window |
| Spatial Consistency Checker | Cross-checks against k-nearest neighbor stations at same timestamp | reads sibling station readings |
| Fault Classifier | Combines rule/ML/spatial signals into a single reason-coded verdict | internal, no external calls |
| Alerts Service | Applies severity thresholds, dedupes, dispatches | Notification channel, WebSocket |
| Storage | Source of truth: raw data, QC verdicts, station metadata, alerts, feedback | everything |
| Dashboard | Visualization + operator interaction | REST API, WebSocket |
| Retraining Job | Periodic/triggered model retrain using operator feedback as labels | DB, model registry (filesystem/S3-like) |

## 3. Data flow — one reading's lifecycle
1. Simulator sends `{station_id, timestamp, temperature, humidity, pressure, wind_speed, wind_dir, rainfall, solar_radiation}`.
2. Ingestion stores it in `raw_readings` (status = `pending`).
3. QC pipeline runs synchronously (or near-real-time via queue) in this order:
   - Rule checks (cheap, catch obvious garbage — e.g. humidity > 100%).
   - ML reconstruction-error score (per-variable, per-station model).
   - Spatial consistency (only if rule/ML score is borderline, to save compute).
   - Classifier merges signals → `valid | suspect | anomalous` + `reason_code` + `confidence`.
4. Result written to `qc_results`, raw reading status updated.
5. If `anomalous` and severity ≥ threshold → Alerts Service fires.
6. Dashboard subscribes via WebSocket, updates map marker color + alerts feed live.
7. Operator opens station detail, sees chart with the flagged point highlighted + reason.
8. Operator clicks Confirm Fault / False Alarm → written to `feedback` table.
9. Nightly (or on-demand) Retraining Job pulls feedback-labeled examples, retrains ML models, bumps model version.

## 4. Module boundaries (for a monolith-but-modular build)
```
/backend
  /ingestion      - FastAPI routes + simulator client
  /qc
    /rules.py
    /ml_scorer.py
    /spatial.py
    /classifier.py
  /alerts
  /storage        - SQLAlchemy models, migrations
  /api            - REST endpoints consumed by frontend
  /retrain        - Celery tasks
/frontend
  /src/pages      - MapView, StationDetail, AlertsFeed, Admin
  /src/components
  /src/api        - typed API client
```
Each module has a single responsibility and a narrow interface — this is what lets "one feature at a time" (see features.md) work without the codebase turning into a tangled mess.

## 5. Scaling path (v1 prototype → production, for judges asking "does this scale")
- Simulator → real AWS telemetry gateway (MQTT/GSM ingestion already common in IMD's field deployments).
- FastAPI single instance → horizontally scaled behind a load balancer; QC pipeline moved to a proper stream processor (Kafka + Flink/Spark Streaming) for 1,000+ station throughput.
- Postgres/Timescale → managed Timescale Cloud or partitioned Postgres; add read replicas for dashboard queries.
- Model retraining → scheduled pipeline (Airflow) with model registry (MLflow) instead of ad-hoc Celery task.
- Add authentication/RBAC (IMD staff roles) before any real deployment.

## 6. Security & reliability notes
- Ingestion endpoint should validate station_id against a known registry (reject spoofed stations).
- Idempotency: dedupe readings by `(station_id, timestamp)` to survive network retries.
- Offline resilience: simulator/edge gateway should support local buffering + batch sync, mirroring the "offline functionality for remote areas" requirement seen across other MoES/disaster-management PSs.
