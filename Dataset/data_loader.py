"""
data_loader.py — AeroSentinel (SIH26073)
Feature: F2 — Historical data loader

Pulls hourly historical weather data for a cluster of real Indian station
locations via Meteostat, and writes it out in a schema that matches the
`raw_readings` table in database.md — so it can be loaded straight into
the DB seed step with no further transformation.

Usage:
    pip install -r requirements.txt
    python data_loader.py --start 2022-01-01 --end 2024-12-31 --stations data/stations.csv --out data/raw_readings.csv

Output columns match database.md `raw_readings`:
    station_id, timestamp, temperature, humidity, pressure,
    wind_speed, wind_direction, rainfall, solar_radiation,
    ingest_source, ingested_at

Notes:
- station_id here is the human-readable station_code from stations.csv
  (F1's DB seed step is responsible for mapping station_code -> UUID
  when it loads stations into the `stations` table; do that lookup at
  DB-load time, not here, so this script has zero DB dependency).
- Meteostat does not provide solar_radiation for most stations reliably;
  missing values are left as NaN/empty, not zero-filled. The QC pipeline
  (F4) must treat that as "sensor not installed" (N/A), never as an
  anomaly-by-omission — see test.md edge cases.
- Units are normalized here so no downstream unit-mismatch can leak into
  the spatial-consistency check (F7): temperature in °C, pressure in hPa,
  wind speed in m/s, rainfall in mm.
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from meteostat import Point, Hourly
except ImportError:
    sys.exit(
        "Missing dependency: run `pip install meteostat pandas` "
        "(or `pip install -r requirements.txt`) before running this script."
    )


def load_stations(stations_csv: str) -> list[dict]:
    with open(stations_csv, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch_station_history(station: dict, start: datetime, end: datetime) -> pd.DataFrame:
    """Fetch hourly history for one station via Meteostat and reshape to our schema."""
    point = Point(float(station["latitude"]), float(station["longitude"]), float(station["elevation_m"]))
    df = Hourly(point, start, end).fetch()

    if df.empty:
        print(f"  [warn] no data returned for {station['station_code']} ({station['name']})")
        return pd.DataFrame()

    # Meteostat's native hourly columns:
    #   temp (°C), rhum (%), pres (hPa), wspd (km/h), wdir (deg), prcp (mm), srad (W/m^2, often missing)
    out = pd.DataFrame({
        "station_id": station["station_code"],
        "timestamp": df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC"),
        "temperature": df["temp"],
        "humidity": df["rhum"],
        "pressure": df["pres"],
        "wind_speed": df["wspd"] / 3.6 if "wspd" in df else None,  # km/h -> m/s
        "wind_direction": df["wdir"] if "wdir" in df else None,
        "rainfall": df["prcp"] if "prcp" in df else None,
        "solar_radiation": df["srad"] if "srad" in df else None,
    })
    out["ingest_source"] = "meteostat_historical"
    out["ingested_at"] = datetime.now(timezone.utc)
    return out


def main():
    parser = argparse.ArgumentParser(description="Load historical AWS-equivalent data via Meteostat.")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--stations", default="data/stations.csv")
    parser.add_argument("--out", default="data/raw_readings.csv")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")

    stations = load_stations(args.stations)
    print(f"Loading {len(stations)} stations from {args.stations}, {args.start} to {args.end}...")

    frames = []
    for station in stations:
        print(f" - {station['station_code']} ({station['name']})")
        df = fetch_station_history(station, start, end)
        if not df.empty:
            frames.append(df)

    if not frames:
        sys.exit("No data fetched for any station. Check station coordinates / date range / network access.")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["station_id", "timestamp"])

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_path, index=False)

    print(f"\nWrote {len(combined):,} rows across {combined['station_id'].nunique()} stations to {out_path}")
    print("\nQuick data-quality summary (missing values per column):")
    print(combined.isna().sum().to_string())
    print(
        "\nNote: missing solar_radiation is expected (see data-sources.md §5) — "
        "do not treat it as a data-loading failure."
    )


if __name__ == "__main__":
    main()
