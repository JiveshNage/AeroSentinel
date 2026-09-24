# techstack.md — AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control

Optimized for: fast solo/small-team build, strong demo, judge-legible architecture, real path to production.

## 1. Overall stack decision
**Python-first backend + ML, React dashboard, Postgres/TimescaleDB storage.** This is the standard, defensible combo for a time-series-heavy, ML-heavy SIH software PS. Avoid over-engineering (no need for Kubernetes/microservices for a hackathon prototype).

## 2. Layer-by-layer

### 2.1 Data ingestion & simulation
- **Python 3.11**
- `FastAPI` — lightweight ingestion API (`POST /ingest`, mimics what a real AWS gateway would call)
- Simulator script (`pandas` + `numpy`) that replays historical CSV/NetCDF weather data station-by-station in time order, with a `--inject-fault` flag to synthetically corrupt a stream (flatline/spike/drift/dropout) for demo purposes
- **MQTT (optional, `paho-mqtt`)** if you want to demo "IoT-style" push ingestion instead of pure REST — nice for judges who know AWS sensor deployments use MQTT/GSM

### 2.2 Storage
- **TimescaleDB** (Postgres extension) — purpose-built for time-series (sensor readings), but you keep normal SQL/Postgres tooling. Alternative: plain Postgres if Timescale setup is a blocker.
- **Redis** — cache of latest per-station status for the dashboard (avoid hammering Postgres for live map refresh), and as a pub/sub channel for pushing alerts to the frontend.

### 2.3 QC / Anomaly detection engine
- `pandas`, `numpy` — rule-based checks (range, step, persistence/flatline)
- `scikit-learn` — `IsolationForest` / `LocalOutlierFactor` for fast, explainable baseline anomaly scoring per station
- `PyTorch` (or `TensorFlow/Keras` if team prefers) — LSTM-Autoencoder for time-series anomaly detection (reconstruction-error based), trained per-sensor-variable
- `scipy.spatial` (KDTree) — nearest-neighbor lookup for spatial consistency checks (compare a station's reading against geographically nearby stations)
- Optional: `PyOD` library — bundles many anomaly-detection algorithms with a consistent API, saves build time

### 2.4 Backend / API
- **FastAPI** (Python) for all REST endpoints — QC results, station CRUD, alerts, feedback capture, model retrain trigger
- `SQLAlchemy` + `Alembic` — ORM + migrations
- `Celery` + Redis (or simple `APScheduler` if time-constrained) — background jobs: periodic QC sweep, scheduled retraining

### 2.5 Frontend / Dashboard
- **React + TypeScript**, bundled with Vite
- `Leaflet` or `Mapbox GL JS` — India map with AWS station markers, color-coded by health status
- `Recharts` or `Plotly.js` — per-station time-series charts with anomaly overlays
- `TailwindCSS` + `shadcn/ui` — fast, clean UI without custom design system work
- WebSocket (FastAPI `websockets` or Socket.IO) — live alert push to dashboard

### 2.6 Alerting
- Email: `SMTP` via a free provider (SendGrid/Mailgun free tier) — good enough for demo
- SMS: stub/mock in MVP (real integration = Twilio, mention as roadmap item — matches other MoES PSs' "SMS-based alert" pattern)

### 2.7 DevOps / deployment
- **Docker + docker-compose** — one command spins up API, Postgres/Timescale, Redis, frontend — critical for judge demo reliability
- Deploy target for demo: any of Render / Railway / a local machine with ngrok — don't over-invest in cloud infra for a hackathon
- `GitHub Actions` — basic CI (lint + test) if time allows, shows engineering maturity to judges

### 2.8 Testing
- `pytest` for backend/ML unit + integration tests
- `Vitest` / `React Testing Library` for frontend

## 3. Why not X
- **Not Kafka**: real IMD-scale streaming would use it, but for a prototype it's overkill; note it in architecture.md as the production upgrade path.
- **Not a full microservices split**: one FastAPI monolith with clear internal module boundaries (ingestion / qc / api / alerts) is faster to build and just as legible to judges; document the seam so it *could* be split later.
- **Not MongoDB**: time-series + relational station metadata fits Postgres/Timescale better than a document store.

## 4. Minimum viable stack (if time is very tight)
FastAPI + SQLite + scikit-learn (IsolationForest only, skip LSTM) + React (or even a single-page HTML+Chart.js dashboard) + Docker. This still demonstrates the full pipeline end-to-end; add Timescale/LSTM/Redis back in as time permits, in that order.
