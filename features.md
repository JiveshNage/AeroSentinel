# features.md — AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control
**Purpose:** Feed the AI *one feature at a time*, in this order. Never say "build the whole app." Each feature below is scoped to be a single focused prompt/session, has explicit inputs/outputs, and a definition of done you can verify before moving to the next.

Rule of thumb: after each feature, run it, look at it, commit it. Then move on.

---

### F0 — Project scaffold
**Build:** Repo structure (`/backend`, `/frontend`), Docker Compose with Postgres+Timescale and Redis, FastAPI "hello world" health-check endpoint, React app that fetches and displays it.
**Done when:** `docker-compose up` gives a working empty app end-to-end.

### F1 — Database schema & migrations
**Build:** SQLAlchemy models for `stations`, `raw_readings`, `qc_results`, `alerts`, `feedback`, `users`, `model_registry` (see database.md). Alembic migration. Seed script for ~20 stations with real lat/long.
**Done when:** Migrations run clean; seed script populates `stations`.

### F2 — Historical data loader + simulator (no fault injection yet)
**Build:** Script to load historical/sample weather CSV into `raw_readings`; a "replay" simulator that posts readings to `/ingest` in time order at configurable speed.
**Done when:** Running the simulator visibly fills `raw_readings` in order.

### F3 — Ingestion API
**Build:** `POST /ingest` endpoint: validate payload shape, dedupe on `(station_id, timestamp)`, persist, return 201/409.
**Done when:** Duplicate posts are rejected; malformed payloads return 422 with a clear error.

### F4 — Rule-based QC layer
**Build:** Pure functions: range check (against `sensor_specs`), step check (delta between consecutive readings too large), persistence/flatline check (N identical consecutive readings). Write results to `qc_results` with `reason_code = RULE_*`.
**Done when:** Unit tests pass for each rule against known good/bad synthetic inputs (see test.md).

### F5 — Fault injection tool
**Build:** CLI/script that takes a clean station stream and injects: flatline, spike, drift, dropout — parameterized by magnitude/duration. Used for both ML training and live demo.
**Done when:** You can visually confirm (via a quick plot) that injected faults look realistic.

### F6 — Baseline ML anomaly scorer (Isolation Forest)
**Build:** Per-station, per-variable IsolationForest trained on a rolling window of "clean" history; scoring function returns an anomaly score for a new reading. Store in `qc_results` with `reason_code = ML_RECON_ERROR` (reuse this code or add `ML_ISOFOREST`).
**Done when:** On the fault-injected test set, model flags injected anomalies at a measurable recall (log precision/recall to a report file).

### F7 — Spatial consistency checker
**Build:** For each reading, find k-nearest stations (via lat/long), compare same-timestamp readings, flag if this station deviates far beyond the neighbor spread (e.g. z-score vs. neighbor distribution). This is what tells the system "everyone's temperature spiked → real heatwave" vs. "only this station spiked → sensor fault."
**Done when:** Demonstrable on a synthetic case: same fault injected at 1 station (flagged) vs. same "event" injected at all nearby stations (not flagged as fault).

### F8 — Fault classifier (merge layer)
**Build:** Combine rule + ML + spatial signals into one verdict (`valid/suspect/anomalous`) + `fault_type` + `confidence`. Simple deterministic scoring/weighting logic is fine for v1 (don't over-engineer a meta-model yet).
**Done when:** Given a labeled test set (from F5's injected faults), classifier report shows precision/recall per fault type.

### F9 — LSTM-Autoencoder upgrade (stretch, do after F8 works)
**Build:** Train an LSTM-AE per key variable on multi-station clean sequences; reconstruction error feeds into the classifier alongside/instead of IsolationForest.
**Done when:** Side-by-side comparison shows LSTM-AE improves recall on drift/flatline cases vs. IsolationForest baseline.

### F10 — Alerts service
**Build:** Rule mapping `verdict + confidence → severity`; on new `anomalous` qc_result, create `alerts` row, push via WebSocket, send stub email.
**Done when:** Injecting a fault via simulator produces a visible alert within seconds.

### F11 — Dashboard: map view
**Build:** React + Leaflet map of all stations, marker color = current health status (pull from Redis cache of latest verdict per station), click marker → station summary popup.
**Done when:** Map correctly reflects live status changes as the simulator runs.

### F12 — Dashboard: station detail view
**Build:** Time-series chart (Recharts) per variable for a selected station, with anomalous points highlighted and reason-code tooltip.
**Done when:** Clicking an alert in the feed jumps to the right station/time window with the anomaly visibly marked.

### F13 — Dashboard: alerts feed + feedback capture
**Build:** Live list of alerts (newest first), each with Confirm Fault / False Alarm buttons → writes to `feedback` table.
**Done when:** Feedback rows appear in DB correctly linked to the right `qc_result_id`.

### F14 — Retraining job
**Build:** Celery task (or manual trigger endpoint for demo) that pulls `feedback`-labeled examples, retrains the ML models, writes a new `model_registry` row, flips `is_active`.
**Done when:** After feeding enough false-alarm feedback for a specific false-positive pattern, a retrain measurably reduces that false positive on a held-out replay.

### F15 — Auth & roles (if time allows)
**Build:** Login, JWT sessions, role-gated routes (`admin` can manage stations/retrain, `field_technician` sees maintenance queue only, etc.)
**Done when:** Role restrictions verifiably enforced (403 for wrong role).

### F16 — Predictive maintenance scoring (stretch)
**Build:** Feature set per station (fault frequency, age, recent drift trend) → simple classifier/regressor predicting failure probability in next 30 days; surfaced as a ranked list.
**Done when:** Ranked list is sane on historical data (stations that did fail rank higher pre-failure than stations that didn't).

### F17 — Polish pass for demo
**Build:** Seed a compelling demo script: replay history → inject a flatline on Station A live → show alert fire → show operator confirm → show retrain improve. Clean up UI rough edges, add loading states, write README with setup instructions.
**Done when:** You can run the full demo script start to finish without manual DB fixes.

---
## How to use this file with an AI coding assistant
Feed one `F#` section at a time as the task. Do not skip ahead. After each feature, ask the assistant to run `code-reviewer.md` and `test.md` against just that feature before starting the next. Update `memory.md` after each feature completes.
