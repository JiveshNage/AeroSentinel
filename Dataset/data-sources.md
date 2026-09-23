# data-sources.md — AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control

**Purpose:** Single reference for where training/demo data comes from, since no public dataset of real, labeled AWS sensor faults exists. Read this before touching F2 (historical loader) or F5 (fault injector) in `features.md`.

## 1. Reality check
IMD's public AWS/ARG portal (`aws.imd.gov.in`) has been locked to the public since ~May 2025 and has not reopened. Real live/historical IMD AWS station data is therefore **not directly obtainable**. This is not a blocker — it's why the architecture treats the data source as swappable (see `architecture.md` §5, Scaling path) — but plan the demo around it instead of discovering it mid-build.

## 2. The three data types needed
1. **Station metadata** — lat/long, elevation, sensor specs. Feeds `stations` table.
2. **Multi-station historical time series** — temperature, humidity, pressure, wind speed/direction, rainfall, solar radiation, at consistent (hourly) intervals, across *multiple geographically clustered stations simultaneously*. Multi-station is non-negotiable — the spatial-consistency check (F7) needs neighbors to compare against.
3. **Labeled fault data** — essentially doesn't exist publicly for weather sensors. Standard approach (used in the actual research literature on this exact problem, e.g. flatline/drift AWS studies): use real clean data + synthetic fault injection to generate labels. This is not a workaround, it's the accepted method.

## 3. Sources, ranked by usefulness for this project

| Source | What it gives | How to access | Use for |
|---|---|---|---|
| **Meteostat** | Clean pandas-friendly wrapper over NOAA ISD + others, queryable by lat/lon/date range | `pip install meteostat`, Python API, no auth needed for the open tier | Primary data loader (F2) — see `data_loader.py` |
| **NOAA ISD (Integrated Surface Database)** | Raw global hourly station data, 1901–present, 35,000+ stations incl. India | `ncei.noaa.gov/products/land-based-station/integrated-surface-database`, free bulk download | Fallback if Meteostat rate-limits or misses a station; source-of-truth Meteostat wraps |
| **NOAA GSOD** | Daily aggregates | Same NCEI portal | Only if hourly granularity isn't needed (not recommended for QC demo — too coarse to show flatline/spike detection well) |
| **data.gov.in** | Government-published climate/rainfall datasets | Search portal directly | Supplementary/backup; check current listing, coverage varies |
| **Kaggle — "Sensor Fault Detection Data" (arashnic)** | Real industrial sensor fault-labeled time series (not weather) | Kaggle dataset search | Reference only — sanity-check that your fault injector's patterns (magnitude, duration, realism) resemble real-world fault shapes |
| **Kaggle — Indian city historical weather datasets** | Single-city long time series | Kaggle dataset search | Backup/filler if a specific region's Meteostat coverage is thin |

## 4. Data plan for the actual build
1. Pick one geographic cluster of ~15–30 real Indian locations close enough together that "spatial consistency" is meaningful (e.g., NCR belt, or a Maharashtra cluster). Coordinates go in `data/stations.csv`.
2. Run `data_loader.py` (see below) to pull 1–3 years of hourly data per station via Meteostat into `raw_readings`-shaped CSVs.
3. Run the fault injector (F5, separate script) against copies of this clean data to produce the labeled flatline/spike/drift/dropout test set used to train and evaluate F6–F9.
4. Keep the loader's output schema identical to `database.md`'s `raw_readings` table so it drops straight into the DB seed step (F1) with no transformation step later.
5. When/if a real IMD feed becomes available again, only the ingestion adapter changes — the QC pipeline, DB schema, and dashboard are unaffected (this is the whole point of keeping ingestion as a separate module per `architecture.md`).

## 5. Known data-quality caveats to handle in F2
- Meteostat/ISD data itself is not perfectly clean — expect some missing hours and occasional real anomalies (e.g. a station's genuine sensor fault already baked into the historical record). Don't assume all "clean" pulled data is actually clean; a quick manual scan / basic rule-check pass before treating it as ground truth for injector baselines is worth doing.
- Solar radiation is the field most likely to be missing/unavailable for a given station — the QC pipeline should treat "not installed at this station" as N/A, not as a fault (see `test.md` edge cases).
- Units: confirm temperature (°C vs °F), pressure (hPa), wind speed (m/s vs knots) are normalized consistently across all pulled stations before loading — a unit mismatch between stations will masquerade as a spatial-consistency "anomaly" and quietly poison F7.
