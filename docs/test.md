# test.md — AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control
Use this as the instruction prompt whenever asking the AI to write or run tests for a feature. Reference the specific `F#` from features.md being tested.

## Testing philosophy for this project
Every feature is only "done" (per features.md) when its test evidence exists — not just "it ran once and looked fine." Anomaly-detection code is especially easy to fool yourself about, so tests must include deliberately adversarial/edge cases, not just happy paths.

## 1. Test pyramid for AeroSentinel

### Unit tests (`pytest`, fast, run on every change)
- **Rule engine (F4)**: for each rule (range/step/flatline), test: a clearly valid reading passes; a clearly invalid reading fails with the right `reason_code`; boundary values (exactly at min/max) behave as documented; missing/null field doesn't crash, produces a sane verdict.
- **Fault injector (F5)**: injected flatline actually produces N identical consecutive values; injected spike is outside normal range by the configured magnitude; injected drift accumulates monotonically; injected dropout produces missing timestamps, not zero values.
- **ML scorer (F6/F9)**: given a fixed random seed and fixed training window, score output is deterministic; a synthetic pure-noise input produces reliably higher anomaly scores than a synthetic clean sinusoid-like weather pattern.
- **Spatial checker (F7)**: with 3+ synthetic neighbor stations reporting consistent values and 1 outlier, outlier is flagged; when all stations move together (simulated real weather event), none are flagged.
- **Classifier merge logic (F8)**: table-driven tests — given (rule_result, ml_score, spatial_result) combinations, assert expected verdict + fault_type.

### Integration tests (`pytest` + test DB / testcontainers)
- Full pipeline: POST a reading to `/ingest` → assert a `qc_results` row is created with expected verdict.
- Duplicate ingestion (same station_id+timestamp twice) → second call rejected, no duplicate `qc_results`.
- Alert firing: post an anomalous reading → assert `alerts` row created and WebSocket message emitted (can mock the WS layer and assert it was called).
- Feedback loop: submit feedback → assert row written and linked correctly; trigger retrain → assert new `model_registry` row with `is_active=true` and old version's `is_active=false`.

### Model evaluation tests (not pass/fail, but tracked reports)
- Build a labeled test set from the fault injector: N clean windows + N windows with each fault type injected, spread across multiple stations.
- Compute precision/recall/F1 **per fault type** (flatline, spike, drift, dropout, spatial-mismatch) — not just an aggregate number, since aggregate can hide a fault type the model is bad at.
- Track these numbers in a checked-in `reports/model_eval_<date>.md` or similar, so regressions are visible across retrains — this doubles as evidence for SIH judges.
- Explicitly test the "real extreme weather, not a fault" case: inject a simultaneous event across many neighboring stations and assert it is NOT classified as `anomalous` (this is the hardest and most important test in the whole system — get it in early).

### End-to-end / demo tests
- Scripted scenario matching the judge demo (see features.md F17): run simulator → inject live flatline → assert dashboard reflects it (can be a Playwright/Cypress test hitting the running frontend, or manually scripted if time-constrained).
- Load test (lightweight): simulate 50 stations reporting every 15 min concurrently, confirm no dropped ingestions and QC pipeline keeps up (rough throughput sanity check, not formal load testing).

### Frontend tests
- Component tests for map marker color logic (given a status, renders correct color).
- Component test for alert feed: confirm/reject buttons call the right API with the right payload.

## 2. Edge cases checklist (specific to weather sensor data — don't skip these)
- New station with zero history — QC must not crash trying to compute a rolling baseline; should default to `suspect`/low-confidence until enough history accumulates.
- Sensor variable entirely absent from a payload (e.g., solar radiation sensor not installed at this station) — should be treated as N/A, not flagged as anomalous-by-omission.
- Legitimate extreme values (cyclone-level wind speed, record heatwave temperature) — must not be auto-flagged as faults; this is what the spatial check exists for.
- Daylight/seasonal patterns — a naive range check might flag normal winter minimums in a cold region as "too low" if thresholds were tuned on a warm-region station; verify per-station thresholds, not global constants.
- Clock skew / out-of-order arrival — a reading arriving late (out of timestamp order) shouldn't corrupt rolling-window calculations.
- Station goes fully offline (no data at all) vs. station sends flatlined data — these are different fault types (`dropout` vs `flatline`) and must be distinguished.

## 3. How to instruct the AI when requesting tests
Always specify: which feature (`F#`), which layer (unit/integration/eval), and remind it to include at least one adversarial case (a real-weather-event look-alike, a malformed payload, a boundary value) — don't let it only write happy-path tests.

## 4. Definition of "tested and working"
A feature is not marked done in `memory.md` until: unit tests pass, at least one integration test covers its main path, and (for QC/ML features) a per-fault-type precision/recall number has been recorded.
