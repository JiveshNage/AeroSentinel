"""
simulator.py — AeroSentinel AWS Station Telemetry Replay Simulator
Feature: F2 — Historical loader + simulator

Replays historical (or synthetic meteorological) sensor readings
station-by-station in time order to the Ingestion API (POST /ingest).

Usage:
    # Replay from CSV to running ingestion API
    python -m ingestion.simulator --input data/raw_readings.csv --url http://127.0.0.1:8000/ingest --delay 0.05

    # Run in sample-generation mode (48 hours of clean multi-station telemetry)
    python -m ingestion.simulator --sample-hours 48 --batch

    # Bulk load historical data directly into database without HTTP overhead
    python -m ingestion.simulator --input data/raw_readings.csv --direct-db
"""

import argparse
import math
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Generator, Optional
import random

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pandas as pd
import requests

from storage.db import SessionLocal
from storage.models import Station, RawReading
from storage.seed import seed_database
from ingestion.schemas import IngestReadingRequest, BatchIngestRequest
from ingestion.service import ingest_reading, ingest_batch


def generate_synthetic_weather_stream(
    stations: List[Station],
    start_time: datetime,
    hours: int = 48,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate realistic diurnal multi-station hourly weather observations."""
    rng = random.Random(seed)
    records = []

    for h in range(hours):
        current_time = start_time + timedelta(hours=h)
        hour_of_day = current_time.hour

        # Regional background meteorological trend (Delhi/NCR diurnal curve)
        # Peak temperature around 14:00 (2 PM), lowest around 05:00
        solar_angle = math.sin(math.pi * (hour_of_day - 8) / 12) if 6 <= hour_of_day <= 19 else 0.0
        base_temp = 32.0 + 8.0 * math.sin(2 * math.pi * (hour_of_day - 9) / 24.0)
        base_rhum = 65.0 - 25.0 * math.sin(2 * math.pi * (hour_of_day - 9) / 24.0)
        base_pres = 1006.0 + 2.0 * math.cos(4 * math.pi * hour_of_day / 24.0)  # semi-diurnal atmospheric tide

        for st in stations:
            # Station-specific geographic offsets
            lat_delta = (st.latitude - 28.5) * -0.4
            elev_delta = (st.elevation_m or 200.0) * -0.0065  # lapse rate ~6.5°C / km
            station_temp = base_temp + lat_delta + (elev_delta + 1.3) + rng.uniform(-0.6, 0.6)
            station_rhum = max(10.0, min(95.0, base_rhum + rng.uniform(-3.0, 3.0)))
            station_pres = base_pres - ((st.elevation_m or 200.0) / 8.5) + rng.uniform(-0.3, 0.3)
            station_wspd = max(0.5, 4.0 + 2.0 * solar_angle + rng.uniform(-1.0, 1.5))
            station_wdir = (270.0 + rng.uniform(-30.0, 30.0)) % 360.0
            station_rain = 0.0  # clean weather by default
            station_srad = max(0.0, 950.0 * solar_angle + rng.uniform(-20.0, 20.0)) if solar_angle > 0 else 0.0

            records.append({
                "station_id": st.station_code,
                "timestamp": current_time.isoformat(),
                "temperature": round(station_temp, 2),
                "humidity": round(station_rhum, 1),
                "pressure": round(station_pres, 1),
                "wind_speed": round(station_wspd, 1),
                "wind_direction": round(station_wdir, 1),
                "rainfall": station_rain,
                "solar_radiation": round(station_srad, 1),
                "ingest_source": "simulator",
            })

    df = pd.DataFrame(records)
    df["dt"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["dt", "station_id"]).drop(columns=["dt"])
    return df


def load_csv_readings(csv_path: Path) -> pd.DataFrame:
    """Load readings CSV and sort in strict chronological order."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Readings file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    required_cols = {"station_id", "timestamp"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"CSV missing required columns: {required_cols - set(df.columns)}")

    df["dt"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("dt").drop(columns=["dt"])
    return df


def run_simulator(
    df: pd.DataFrame,
    url: str,
    delay: float = 0.05,
    limit: Optional[int] = None,
    batch_mode: bool = False,
    direct_db: bool = False,
) -> int:
    """Replay sensor readings in time order to ingestion endpoint or database."""
    total_rows = len(df) if limit is None else min(len(df), limit)
    print(f"Starting AeroSentinel simulator replay: {total_rows} readings, delay={delay}s, mode={'direct-db' if direct_db else 'HTTP'}")

    if direct_db:
        session = SessionLocal()
        try:
            inserted = 0
            for _, row in df.head(total_rows).iterrows():
                req = IngestReadingRequest(
                    station_id=str(row["station_id"]),
                    timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(),
                    temperature=float(row["temperature"]) if pd.notna(row.get("temperature")) else None,
                    humidity=float(row["humidity"]) if pd.notna(row.get("humidity")) else None,
                    pressure=float(row["pressure"]) if pd.notna(row.get("pressure")) else None,
                    wind_speed=float(row["wind_speed"]) if pd.notna(row.get("wind_speed")) else None,
                    wind_direction=float(row["wind_direction"]) if pd.notna(row.get("wind_direction")) else None,
                    rainfall=float(row["rainfall"]) if pd.notna(row.get("rainfall")) else None,
                    solar_radiation=float(row["solar_radiation"]) if pd.notna(row.get("solar_radiation")) else None,
                    ingest_source=str(row.get("ingest_source", "simulator")),
                )
                try:
                    ingest_reading(session, req)
                    inserted += 1
                except Exception:
                    pass  # skip duplicate in bulk mode

                if inserted % 100 == 0:
                    print(f"  [direct-db] inserted {inserted}/{total_rows} readings...")
            print(f"Direct DB bulk insertion complete: {inserted} readings committed.")
            return inserted
        finally:
            session.close()

    # HTTP replay mode
    ingested_count = 0
    grouped = df.head(total_rows).groupby("timestamp", sort=False)

    for ts_str, group in grouped:
        readings_list = []
        for _, row in group.iterrows():
            reading_dict = {
                "station_id": str(row["station_id"]),
                "timestamp": str(row["timestamp"]),
                "temperature": float(row["temperature"]) if pd.notna(row.get("temperature")) else None,
                "humidity": float(row["humidity"]) if pd.notna(row.get("humidity")) else None,
                "pressure": float(row["pressure"]) if pd.notna(row.get("pressure")) else None,
                "wind_speed": float(row["wind_speed"]) if pd.notna(row.get("wind_speed")) else None,
                "wind_direction": float(row["wind_direction"]) if pd.notna(row.get("wind_direction")) else None,
                "rainfall": float(row["rainfall"]) if pd.notna(row.get("rainfall")) else None,
                "solar_radiation": float(row["solar_radiation"]) if pd.notna(row.get("solar_radiation")) else None,
                "ingest_source": str(row.get("ingest_source", "simulator")),
            }
            readings_list.append(reading_dict)

        if batch_mode:
            batch_url = url.replace("/ingest", "/ingest/batch") if url.endswith("/ingest") else f"{url}/batch"
            try:
                resp = requests.post(batch_url, json={"readings": readings_list}, timeout=5.0)
                if resp.status_code in (200, 201):
                    res_data = resp.json()
                    ingested_count += res_data.get("ingested", 0)
                    print(f"[{ts_str}] Batch replay: {res_data.get('ingested')} ingested, {res_data.get('duplicates_skipped')} skipped")
                else:
                    print(f"  [warn] batch HTTP {resp.status_code}: {resp.text}")
            except requests.RequestException as e:
                print(f"  [error] HTTP connection failed: {e}")
        else:
            for item in readings_list:
                try:
                    resp = requests.post(url, json=item, timeout=5.0)
                    if resp.status_code in (200, 201):
                        ingested_count += 1
                        print(f"[{ts_str}] Replayed {item['station_id']}: temp={item['temperature']}°C, rhum={item['humidity']}% -> 201 Created")
                    elif resp.status_code == 409:
                        print(f"[{ts_str}] Replayed {item['station_id']}: duplicate skipped (409 Conflict)")
                    else:
                        print(f"  [warn] {item['station_id']} HTTP {resp.status_code}: {resp.text}")
                except requests.RequestException as e:
                    print(f"  [error] HTTP connection failed for {item['station_id']}: {e}")

        if delay > 0:
            time.sleep(delay)

    print(f"Simulator replay finished. Successfully ingested {ingested_count} readings.")
    return ingested_count


def main():
    parser = argparse.ArgumentParser(description="AeroSentinel AWS Telemetry Replay Simulator")
    parser.add_argument("--input", type=str, default=None, help="Path to historical raw readings CSV")
    parser.add_argument("--url", type=str, default="http://127.0.0.1:8000/ingest", help="Ingestion API endpoint")
    parser.add_argument("--delay", type=float, default=0.02, help="Delay in seconds between timestamps")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of readings to replay")
    parser.add_argument("--sample-hours", type=int, default=48, help="Hours of sample weather data to generate if no CSV")
    parser.add_argument("--batch", action="store_true", help="Use /ingest/batch endpoint for bulk posting")
    parser.add_argument("--direct-db", action="store_true", help="Insert directly into DB bypassing HTTP")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else None
    if input_path and input_path.exists():
        print(f"Loading readings from CSV: {input_path}")
        df = load_csv_readings(input_path)
    else:
        print(f"No CSV provided or file not found. Generating {args.sample_hours} hours of clean multi-station telemetry...")
        session = SessionLocal()
        try:
            stations = session.query(Station).all()
            if not stations:
                print("No stations registered. Running station seeder...")
                seed_database(session)
                stations = session.query(Station).all()
            now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            start_time = now - timedelta(hours=args.sample_hours)
            df = generate_synthetic_weather_stream(stations, start_time, hours=args.sample_hours)
        finally:
            session.close()

    run_simulator(
        df=df,
        url=args.url,
        delay=args.delay,
        limit=args.limit,
        batch_mode=args.batch,
        direct_db=args.direct_db,
    )


if __name__ == "__main__":
    main()
