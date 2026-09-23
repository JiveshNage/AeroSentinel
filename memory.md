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
| F2 | Historical loader + simulator | ⬜ | |
| F3 | Ingestion API | ⬜ | |
| F4 | Rule-based QC layer | ⬜ | |
| F5 | Fault injection tool | ⬜ | |
| F6 | Baseline ML scorer (IsolationForest) | ⬜ | |
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
| | | | | | | |

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

- `2026-09-23` — F1 complete: Database schema, Alembic migration lifecycle, and station seeder (20 stations) implemented with 13/13 passing tests.
- `2026-09-23` — F0 complete: Scaffolded repo, Docker Compose, FastAPI health check (/api/health), React/Vite dashboard shell with design.md tokens, 5/5 unit tests passing.

---
## Session handoff template
When starting a new AI session, paste this filled-in block first:

```
Current state: [which F# just completed, what's next per features.md]
Known issues: [pull from Known Issues section above]
Do not re-litigate: [any settled architecture/tech decisions from Decision Log — don't let the AI suggest re-doing these without new evidence]
```
