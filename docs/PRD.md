# PRD.md — AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control
**Problem Statement:** SIH26073 — AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations (AWS)
**Sponsor:** Ministry of Earth Sciences (MoES) / India Meteorological Department (IMD)
**Theme:** Disaster Management

---

## 1. Problem, in plain terms
IMD operates 1,000+ Automatic Weather Stations (AWS) across India that stream temperature, humidity, pressure, rainfall, wind speed/direction and solar radiation in near-real-time. These feed forecasts, cyclone tracking, and early warnings.

Sensors fail silently: they drift out of calibration, get stuck ("flatline"), spike from electrical noise, disagree with neighboring stations, or drop data during network outages. Today this is mostly caught by manual inspection or simple threshold rules — too slow and too coarse. A single bad AWS feeding a forecast model or an early-warning pipeline can corrupt outputs region-wide, which is dangerous for a disaster-management use case.

## 2. Goal
Build a software system that ingests AWS sensor streams, automatically flags anomalous/faulty readings in near-real-time using a layered rule-based + statistical + ML approach, classifies the *likely cause* (sensor fault vs. genuine extreme weather), and gives IMD operators a dashboard + alerting workflow to act on it — while continuously learning from operator feedback.

## 3. Non-goals (v1)
- Not building new physical sensors/hardware.
- Not replacing IMD's forecasting models — this is a data-quality/QC layer upstream of them.
- Not doing full nationwide production deployment — target is a working, demo-able prototype on a representative subset of stations (real or simulated data).

## 4. Users & personas
| Persona | Need |
|---|---|
| IMD Data Quality Officer | Sees network-wide health, triages flagged anomalies, confirms/rejects them |
| IMD Regional Forecaster | Wants confidence flags on incoming data before using it in nowcasting |
| Field Maintenance Technician | Gets a prioritized list of stations likely to need physical repair |
| System Admin | Manages station metadata, thresholds, model retraining |

## 5. Core use cases
1. Ingest a stream/batch of AWS readings → run QC pipeline → tag each reading as `valid / suspect / anomalous` with a reason code.
2. Detect **flatline** (sensor stuck), **spike** (implausible jump), **drift** (slow calibration decay), **spatial inconsistency** (disagrees with nearby stations), **missing/dropout** data.
3. Distinguish **sensor fault** vs **real extreme weather event** (e.g., a genuine heatwave shouldn't be flagged as a "spike fault").
4. Dashboard: map of all stations color-coded by health, drill into any station's time series with anomalies overlaid.
5. Alerting: push notification/email/SMS-stub when a station goes anomalous, with severity.
6. Operator feedback loop: mark a flagged anomaly as "confirmed fault" / "false alarm" → stored for model retraining.
7. Predictive maintenance: rank stations by probability of failure in next N days based on historical fault patterns.

## 6. Success metrics
- Precision/recall of anomaly detector against a labeled/injected-fault test set (target: recall ≥ 0.85, precision ≥ 0.75 as a hackathon-realistic bar).
- Detection latency: flag within 1 reading cycle (~15–60 min, matching AWS reporting interval) of anomaly onset.
- False-alarm rate low enough that operators don't ignore alerts (< 1 false alarm / station / week in demo data).
- Judges can see: live dashboard, injected-fault demo, before/after data-quality comparison, and the feedback-retrain loop working end-to-end.

## 7. Key differentiators for SIH judging
- **Explainability**: every flag comes with a reason (which check fired, confidence score) — not a black box.
- **Sensor-fault vs. weather-event distinction** using spatial cross-validation against neighboring AWS — this is the hardest and most judge-impressive part.
- **Human-in-the-loop retraining**, not a static model.
- **Offline/low-connectivity resilience** in line with other MoES PSs (batch sync fallback).

## 8. Constraints & assumptions
- Real IMD AWS data is not publicly available at full resolution → use IMD open data samples / NOAA ISD / synthetic data with injected faults for training & demo, architected so real IMD feeds can be swapped in later.
- Must run as a working demo within hackathon timeframe (36–48 hrs build + prep).
- Small team, must be buildable feature-by-feature (see features.md).

## 9. High-level scope for the 36-hr build (MVP)
1. Data ingestion + simulator (replays historical/synthetic AWS data, can inject faults on demand).
2. Rule-based QC layer (range, step, persistence checks).
3. ML anomaly layer (LSTM-Autoencoder or Isolation Forest per-station + spatial consistency check).
4. Fault classification (flatline/spike/drift/dropout/spatial-mismatch).
5. Dashboard (map + station detail + alerts feed).
6. Feedback capture + simple retrain trigger.

## 10. Stretch goals (post-MVP)
- Predictive maintenance scoring.
- Multi-lingual alerts, SMS integration.
- Integration hooks for IMD's real data pipeline / API.
