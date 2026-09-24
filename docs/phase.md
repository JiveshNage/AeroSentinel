# phase.md — AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control

Phases group the `features.md` items into deliverable milestones. Don't start a phase until the previous one's exit criteria are met — each phase should leave you with something that *runs*, even if incomplete, so you're never far from a demo-able state.

---

## Phase 0 — Foundation (½ day)
**Features:** F0, F1
**Goal:** Empty-but-real skeleton running end to end.
**Exit criteria:**
- `docker-compose up` brings up API + DB + Redis + frontend with zero manual steps.
- DB schema matches `database.md`, migrations apply cleanly, seed data loads.

## Phase 1 — Data pipeline (½–1 day)
**Features:** F2, F3, F5
**Goal:** Can get realistic (and fault-injected) AWS data flowing into the system.
**Exit criteria:**
- Simulator replays historical data into `/ingest` in correct time order.
- Duplicate/malformed payloads correctly rejected.
- Fault injector produces visibly realistic flatline/spike/drift/dropout patterns (spot-check with a plot).

## Phase 2 — Core QC & anomaly detection (1–1.5 days — this is the heart of the project)
**Features:** F4, F6, F7, F8
**Goal:** The actual "intelligent anomaly detection" the PS asks for, working and measured.
**Exit criteria:**
- Rule engine catches obvious garbage with correct reason codes (F4 tests pass).
- ML scorer trained and evaluated on fault-injected test set with recorded precision/recall.
- Spatial checker correctly distinguishes single-station fault from real widespread weather event (this is the single most important exit criterion for this PS — do not skip verifying it).
- Classifier merges all three into a final verdict + fault_type + confidence, logged to `qc_results`.
- **Checkpoint:** run `test.md`'s model evaluation tests and record numbers in `memory.md`.

## Phase 3 — Operator-facing product (1–1.5 days)
**Features:** F10, F11, F12, F13
**Goal:** A human can actually see and act on what the system detects — this is what judges will interact with.
**Exit criteria:**
- Live alert fires within seconds of an injected anomaly.
- Map view shows correct real-time station health.
- Station detail view shows time series with anomalies clearly marked and explained (reason code visible).
- Operator can confirm/reject an alert and it's persisted.

## Phase 4 — Learning loop (½–1 day)
**Features:** F14
**Goal:** Prove the system isn't static — it improves from operator feedback, which is a key judge-facing differentiator.
**Exit criteria:**
- Retraining job runs (manually triggered is fine for demo) using `feedback` data.
- New model version recorded in `model_registry`, old version deactivated.
- Demonstrable before/after: a previously-false-positive pattern is no longer flagged after retrain with enough "false alarm" feedback.

## Phase 5 — Stretch goals (time-permitting, in priority order)
**Features:** F9 (LSTM-AE), F16 (predictive maintenance), F15 (auth/roles)
**Goal:** Depth for judges who dig deeper, not required for a working demo.
**Exit criteria (per item, do whichever fits remaining time):**
- F9: side-by-side eval showing LSTM-AE beats IsolationForest baseline on drift specifically.
- F16: ranked failure-risk list that's plausible against historical fault history.
- F15: basic role gating functional.

## Phase 6 — Demo readiness (½ day, do not skip or compress this)
**Features:** F17
**Goal:** A reliable, rehearsed, judge-proof demo.
**Exit criteria:**
- Scripted demo flow (per features.md F17) runs start-to-finish with no manual DB intervention.
- README lets a judge (or teammate) spin up the whole system from scratch in under 10 minutes.
- Fallback plan exists if live internet/demo environment fails (recorded video backup, or a pre-seeded "already anomalous" state to show immediately without waiting for the simulator).
- Pitch deck/slides map directly to PRD.md's success metrics and differentiators — judges should be able to see the precision/recall numbers, not just take your word for it.

---

## Suggested time allocation (36–48 hr hackathon build)
| Phase | Hours |
|---|---|
| 0 — Foundation | 3–4 |
| 1 — Data pipeline | 5–6 |
| 2 — Core QC/ML | 10–12 |
| 3 — Dashboard | 8–10 |
| 4 — Learning loop | 4–5 |
| 5 — Stretch | remaining time |
| 6 — Demo readiness | 3–4 (non-negotiable, protect this time) |

If running behind, cut from Phase 5 first, then trim Phase 3 to map-view + basic alerts feed only (drop station detail polish) — never cut Phase 2 (it's the actual problem statement) or Phase 6 (an unrehearsed demo loses more points than a missing stretch feature).
