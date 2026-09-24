# debug.md — AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control
Use this as the instruction prompt whenever something is broken and you ask the AI to fix it. The point: force root-cause analysis before any code change, so the AI doesn't randomly mutate code until symptoms disappear.

## Protocol — follow every step, in order, before editing any code

### Step 1 — Reproduce
- State the exact steps to reproduce the bug (command run, endpoint called, payload sent, UI action taken).
- Confirm it's reproducible at least twice. If not reliably reproducible, say so explicitly — this changes the investigation approach (likely a race condition, timing issue, or ordering bug — common in the QC pipeline and WebSocket alerts).
- Capture the exact error: full stack trace, HTTP status + body, or (for silent bugs like a wrong anomaly verdict) the actual vs. expected output with the specific input data.

### Step 2 — Localize
- Which layer is misbehaving? Use `architecture.md`'s module boundaries to bisect: ingestion → rules → ML scorer → spatial checker → classifier → alerts → dashboard. Don't guess across the whole stack at once.
- Add/check logging at the boundary between the last-known-good layer and the first-suspect layer. For the QC pipeline specifically, log the intermediate output of each of the 4 sub-checks (rule/ML/spatial/classifier) for the specific reading in question — not just the final verdict.
- If it's a data problem (wrong values, not a crash): pull the exact row(s) from `raw_readings` and `qc_results` for the station/timestamp in question and inspect manually before touching code.

### Step 3 — Form a hypothesis
- State a specific, falsifiable hypothesis for the root cause (e.g., "the flatline check compares floats with `==`, so tiny floating-point noise from the simulator prevents exact matches, so flatline never fires"). Not "something's wrong with the rules."
- If there are multiple plausible hypotheses, list them ranked by likelihood, and say what evidence would confirm/rule out each — don't just pick one and start editing.

### Step 4 — Confirm the hypothesis with evidence
- Write a minimal test or a one-off script/query that isolates the hypothesized cause, independent of the full pipeline. E.g., for the float-equality example: a 3-line pytest reproducing the flatline check against known-flatlined data and showing it fails.
- Do not proceed to a fix until the hypothesis is confirmed this way. If it's disproven, go back to Step 3.

### Step 5 — Fix at the root, not the symptom
- The fix should address the confirmed root cause, not paper over the symptom. (E.g., use a tolerance-based comparison or round consistently — not "add a special case for this one station.")
- Check `architecture.md`/`database.md` for whether the same root cause could be present elsewhere (e.g., other float-equality comparisons anywhere else in the QC code) — fix all instances, not just the one that surfaced.

### Step 6 — Regression test
- Add a test (per `test.md`) that would have caught this bug, so it can't silently reappear.
- Re-run the full relevant test suite (not just the new test) to confirm nothing else broke.

### Step 7 — Document
- Add a one-line entry to `memory.md`'s changelog: what broke, root cause, fix, and the new regression test's name/location.

## Common root-cause categories specific to this project (check these first)
- **Timezone/naive-datetime mismatches** between simulator, ingestion, and stored timestamps — a classic source of "reading appears in the wrong time bucket" bugs.
- **Float equality / floating-point drift** in rule-based checks (flatline especially).
- **Stale model artifact** — dashboard/QC using an old `model_registry` version because `is_active` flip wasn't atomic, or model wasn't reloaded after retrain.
- **Cache staleness** — Redis cache of "latest station status" not invalidated after a new `qc_results` row, so dashboard shows outdated health.
- **Ordering/race conditions** — WebSocket alert arriving before the DB write it depends on has committed (read-after-write consistency).
- **Threshold source confusion** — code accidentally using a global constant instead of the per-station `sensor_specs` thresholds.
- **Train/test contamination** — a "why is my model suspiciously perfect" bug is almost always data leakage; check `code-reviewer.md` section 3 first.

## What "randomly changing code" looks like (avoid this)
- Editing the QC threshold number without evidence it's actually wrong.
- Adding `try/except: pass` to make an error disappear without understanding why it's thrown.
- Rewriting a whole function "just in case" instead of the one confirmed-bad line.
- Restarting services repeatedly hoping the bug goes away on its own (fine as a reproduction-narrowing step, never as "the fix").
