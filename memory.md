# memory.md — AeroSentinel Project Memory
**AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control**
**Purpose:** Single source of truth for "what has actually been built, tested, and decided" across sessions. Update this at the end of every session / after every feature from `features.md`. Paste the current version of this file at the start of a new AI session so it has full project context instead of re-explaining everything from scratch.

---

## How to update this file
After finishing a feature: append to the changelog, flip its status in the Feature Tracker, note any new decisions in Decision Log, note any known issues. Keep entries short and factual — this file is read by an AI, not a human audience, so prioritize signal density over prose.

---

## Project identity
- **Name:** AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control
- **Problem statement:** SIH26073 — AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations (AWS)
- **Repo root:** _(fill in path/URL once created)_
- **Team:** _(fill in)_
- **Reference docs:** PRD.md, techstack.md, architecture.md, database.md, features.md, code-reviewer.md, test.md, debug.md, phase.md — all in project root.

## Feature tracker
*(status: ⬜ not started / 🟨 in progress / ✅ done+tested / ⚠️ blocked)*

| # | Feature | Status | Notes |
|---|---|---|---|
| F0 | Project scaffold | ✅ | Scaffold complete, FastAPI health check + React/Tailwind frontend |
| F1 | DB schema & migrations | ✅ | SQLAlchemy models for all database.md tables, Alembic migration 56bc0451d50b, 20 seeded stations |
| F2 | Historical loader + simulator | ✅ | Meteostat loader + telemetry replay simulator with offline diurnal generation |
| F3 | Ingestion API | ✅ | POST /ingest and /ingest/batch with deduplication, station registry validation, and 409/422 responses |
| F4 | Rule-based QC layer | ✅ | Pure range, step (circular wind direction wrap), and persistence checks with meteorological zero exemptions; DB persistence to qc_results; 21 tests |
| F5 | Fault injection tool | ✅ | Parameterized fault injector (flatline, spike, drift, dropout, spatial, extreme weather), spotcheck plot reports/injected_faults_spotcheck.png, 11 tests |
| F6 | Baseline ML scorer (IsolationForest) | ✅ | IsolationForest baseline per variable, 6D feature engineering, model registry, benchmark eval report (100% spike, 75% flatline, 58% drift recall) |
| F7 | Spatial consistency checker | ⬜ | |
| F8 | Fault classifier (merge layer) | ⬜ | |
| F9 | LSTM-Autoencoder upgrade | ⬜ | stretch |
| F10 | Alerts service | ⬜ | |
| F11 | Dashboard: map view | ⬜ | |
| F12 | Dashboard: station detail | ⬜ | |
| F13 | Dashboard: alerts feed + feedback | ⬜ | |
| F14 | Retraining job | ⬜ | |
| F15 | Auth & roles | ⬜ | stretch |
| F16 | Predictive maintenance | ⬜ | stretch |
| F17 | Demo polish pass | ⬜ | |

## Decision log
*(Append-only. Each entry: date, decision, why, what alternative was rejected.)*

- `2026-09-23` — Implemented F6 Baseline ML Anomaly Scorer (Isolation Forest) in backend/qc/ml_scorer.py. Engineered 6D feature vector (value, 1-step delta, rolling mean diff, rolling std, cyclical diurnal hour sin/cos). Serialized StandardScaler with ModelBundle to eliminate train/inference skew. Implemented benchmark evaluator and recorded per-fault-type metrics in reports/model_eval_isolation_forest.json.
- `2026-09-23` — Implemented F4 Rule-based QC layer in backend/qc/rules.py. Dynamically loads range and step thresholds from station.sensor_specs. Supports circular angular delta for wind_direction wrap around North (0°/360°), and provides physical domain exemptions for dry-weather zero rainfall and nighttime zero solar radiation during persistence checks. Integrated synchronous first-pass QC execution into ingestion service.
- `2026-09-23` — Implemented F5 Fault Injection Tool in backend/qc/fault_injector.py supporting flatline, spike, drift, and dropout (both physical missing rows and sensor disconnection NaNs, never zero-filled per test.md). Added multi-station labeled benchmark generator and visual 4-panel verification plot in reports/injected_faults_spotcheck.png adhering to design.md palette.
- `2026-09-23` — Implemented F3 Ingestion API (POST /ingest and POST /ingest/batch) supporting station resolution by code and UUID, deduplication returning 409 Conflict, Pydantic bounds checking, and spoofed station rejection (404). Mounted at both /ingest (matching architecture.md gateway spec) and /api/ingest.
- `2026-09-23` — Implemented F2 Telemetry Replay Simulator in backend/ingestion/simulator.py with chronological multi-station replay, configurable delay/batching, CSV loader, and built-in diurnal synthetic generator for offline resilience.
- `2026-09-23` — Implemented all database.md models in backend/storage/models.py using BigIntPK with SQLite Integer variant for multi-engine autoincrement compatibility. Generated initial Alembic migration 56bc0451d50b_create_initial_schema.py. Created idempotent seed script backend/storage/seed.py populating 20 stations with sensor_specs and default operator user.
- `2026-09-23` — Scaffolded F0 strictly following architecture.md module boundaries (/backend with ingestion, qc, alerts, storage, api, retrain; /frontend with src/pages, src/components, src/api). Used FastAPI with Pydantic settings and React 18 + TypeScript + Vite + Tailwind configured with exact CSS custom properties and IBM Plex typography from design.md.
- `2026-09-23` — Configured root docker-compose.yml defining timescale/timescaledb:latest-pg15, redis:7-alpine, backend, and frontend with proper healthchecks and dependencies.

## Known issues / tech debt
*(Things intentionally deferred, or bugs known but not yet fixed. Link to debug.md investigation if one was done.)*

- Host machine lacks `docker` executable (`command not found: docker`). Docker Compose and Dockerfiles are fully configured for when Docker is installed; local execution via Python venv and Node/npm is active and functional.
- Headless browser subagent hit remote CDN 404 downloading Playwright driver for macOS ARM64; verified frontend build via `npm run build` (passed in 689ms) and backend endpoints via curl and pytest (5/5 passed).

## Model performance log
*(Append a row every time models are trained/retrained — this is separate from feature status because it changes independent of feature completion.)*

| Date | Model | Variable | Precision | Recall | F1 | Notes |
|---|---|---|---|---|---|---|
| 2026-09-23 | IsolationForest (v1.0.0) | temperature | 0.2958 | 0.6364 | 0.4038 | Baseline ML on F5 benchmark: Spikes recall=1.0, Flatlines recall=0.75, Drift recall=0.58. Precision will be boosted by F7 spatial checker and F8 classifier merge layer. |

## Data sources in use
- Stations metadata: Dataset/stations.csv (15 NCR stations + 5 additional Indian metropolitan/high-altitude AWS stations)
- Historical loader: Dataset/data_loader.py (Meteostat)

## Environment / setup facts an AI should know without asking
- Backend: FastAPI, Python 3.13 (venv: `.venv`), runs via `docker-compose up` or `uvicorn main:app`
- DB: Postgres+TimescaleDB, migrations via Alembic
- Frontend: React+TS+Vite, Tailwind, IBM Plex Sans / Mono fonts
- Test command(s): `pytest backend/tests -v` (backend), `npm run build` (frontend)
- Ports: Backend `:8000`, Frontend `:5173` (Vite) / `:3000` (Docker)

## Changelog
*(One line per completed feature or significant fix. Newest at top.)*

- `2026-09-23` — F6 complete: Baseline ML anomaly scorer (IsolationForest) implemented with 6D feature engineering, model registry versioning, benchmark evaluation (60/60 tests passing total).
- `2026-09-23` — F4 complete: Rule-based QC layer implemented with range, circular step, and persistence checks, DB persistence to qc_results, and 21 unit/integration tests (53/53 tests passing total).
- `2026-09-23` — F5 complete: Fault injection tool implemented with 4-panel visual verification plot (reports/injected_faults_spotcheck.png) and 11 unit/adversarial tests (32/32 tests passing total). Concludes Phase 1 per phase.md.
- `2026-09-23` — F3 & F2 complete: Ingestion API (single/batch, deduplication, validation) and telemetry replay simulator implemented with 21/21 passing backend tests.
- `2026-09-23` — F1 complete: Database schema, Alembic migration lifecycle, and station seeder (20 stations) implemented with 13/13 passing tests.
- `2026-09-23` — F0 complete: Scaffolded repo, Docker Compose, FastAPI health check (/api/health), React/Vite dashboard shell with design.md tokens, 5/5 unit tests passing.

---
## Session handoff template
When starting a new AI session, paste this filled-in block first:

```
Current state: F6 complete. Next is Phase 2: F7 (Spatial consistency checker).
Known issues: [pull from Known Issues section above]
Do not re-litigate: [any settled architecture/tech decisions from Decision Log — don't let the AI suggest re-doing these without new evidence]
```
