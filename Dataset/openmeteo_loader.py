"""
openmeteo_loader.py — AeroSentinel (SIH26073)
Feature: F2 — Open-Meteo Historical Archive & Reanalysis Data Loader

Pulls hourly and daily meteorological data via the Open-Meteo Archive API
with automatic retry backoff and caching, mapped directly into the AeroSentinel
`raw_readings` schema for multi-station QC and spatial consistency evaluation.

Usage:
    # Pull data for all registered Indian AWS stations:
    python openmeteo_loader.py --start 2024-05-01 --end 2024-05-15 --stations stations.csv --out raw_readings.csv

    # Pull data for a single coordinate:
    python openmeteo_loader.py --start 2024-05-01 --end 2024-05-15 --lat 28.5822 --lon 77.2066 --station-id NCR001
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd

try:
    import openmeteo_requests
    import requests_cache
    from retry_requests import retry
except ImportError:
    sys.exit(
        "Missing dependency: run `pip install openmeteo-requests requests-cache retry-requests numpy pandas` "
        "before running this script."
    )


def get_openmeteo_client(cache_path: str = ".cache", expire_after: int = -1, retries: int = 5):
    """Setup cached Open-Meteo API client with exponential retry backoff."""
    cache_session = requests_cache.CachedSession(cache_path, expire_after=expire_after)
    retry_session = retry(cache_session, retries=retries, backoff_factor=0.2)
    return openmeteo_requests.Client(session=retry_session)


def fetch_openmeteo_hourly(
    client: Any,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    station_id: str = "AWS001",
) -> pd.DataFrame:
    """
    Fetch hourly historical weather parameters for a given coordinate
    and transform into AeroSentinel's raw_readings schema.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "surface_pressure",
            "rain",
            "wind_speed_10m",
            "wind_direction_10m",
            "direct_normal_irradiance",
        ],
        "wind_speed_unit": "ms",  # normalized to m/s
        "timezone": "UTC",
    }

    responses = client.weather_api(url, params=params)
    if not responses:
        return pd.DataFrame()

    response = responses[0]
    hourly = response.Hourly()

    # Extract NumPy series for each variable requested
    temp = hourly.Variables(0).ValuesAsNumpy()
    humidity = hourly.Variables(1).ValuesAsNumpy()
    pressure = hourly.Variables(2).ValuesAsNumpy()
    rain = hourly.Variables(3).ValuesAsNumpy()
    wind_speed = hourly.Variables(4).ValuesAsNumpy()
    wind_direction = hourly.Variables(5).ValuesAsNumpy()
    solar_radiation = hourly.Variables(6).ValuesAsNumpy()

    # Construct continuous UTC timestamp range
    time_index = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left",
    )

    df = pd.DataFrame({
        "station_id": station_id,
        "timestamp": time_index.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "temperature": np.round(temp, 2),
        "humidity": np.round(humidity, 1),
        "pressure": np.round(pressure, 1),
        "wind_speed": np.round(wind_speed, 2),
        "wind_direction": np.round(wind_direction, 0),
        "rainfall": np.round(rain, 2),
        "solar_radiation": np.round(solar_radiation, 1),
        "ingest_source": "openmeteo_archive",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    })

    return df


def fetch_openmeteo_daily(
    client: Any,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch daily aggregated weather parameters for meteorological analysis."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": [
            "weather_code",
            "precipitation_sum",
            "rain_sum",
            "apparent_temperature_mean",
            "temperature_2m_min",
            "temperature_2m_mean",
            "temperature_2m_max",
        ],
        "timezone": "UTC",
    }

    responses = client.weather_api(url, params=params)
    if not responses:
        return pd.DataFrame()

    response = responses[0]
    daily = response.Daily()

    time_index = pd.date_range(
        start=pd.to_datetime(daily.Time(), unit="s", utc=True),
        end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=daily.Interval()),
        inclusive="left",
    )

    df = pd.DataFrame({
        "date": time_index.strftime("%Y-%m-%d"),
        "weather_code": daily.Variables(0).ValuesAsNumpy(),
        "precipitation_sum": daily.Variables(1).ValuesAsNumpy(),
        "rain_sum": daily.Variables(2).ValuesAsNumpy(),
        "apparent_temp_mean": daily.Variables(3).ValuesAsNumpy(),
        "temp_min": daily.Variables(4).ValuesAsNumpy(),
        "temp_mean": daily.Variables(5).ValuesAsNumpy(),
        "temp_max": daily.Variables(6).ValuesAsNumpy(),
    })

    return df


def load_stations_csv(csv_path: str) -> List[Dict[str, Any]]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser(description="Load historical AWS telemetry via Open-Meteo Archive API.")
    parser.add_argument("--start", default="2024-05-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-05-07", help="End date (YYYY-MM-DD)")
    parser.add_argument("--stations", default="stations.csv", help="Path to stations.csv")
    parser.add_argument("--out", default="raw_readings_openmeteo.csv", help="Output CSV path")
    parser.add_argument("--lat", type=float, help="Single station latitude")
    parser.add_argument("--lon", type=float, help="Single station longitude")
    parser.add_argument("--station-id", default="NCR001", help="Station ID for single-coordinate query")
    args = parser.parse_args()

    client = get_openmeteo_client()

    frames = []
    if args.lat is not None and args.lon is not None:
        print(f"Fetching Open-Meteo hourly observations for {args.station_id} ({args.lat}, {args.lon})...")
        df = fetch_openmeteo_hourly(client, args.lat, args.lon, args.start, args.end, station_id=args.station_id)
        if not df.empty:
            frames.append(df)
    else:
        # Load from stations CSV
        stations_path = Path(args.stations)
        if not stations_path.exists():
            stations_path = Path(__file__).parent / "stations.csv"
        if not stations_path.exists():
            sys.exit(f"Stations file not found at {args.stations}")

        stations = load_stations_csv(str(stations_path))
        print(f"Loading Open-Meteo hourly data for {len(stations)} stations from {args.start} to {args.end}...")
        for s in stations:
            st_code = s.get("station_code") or s.get("station_id") or "STATION"
            lat = float(s["latitude"])
            lon = float(s["longitude"])
            print(f" - {st_code} ({s.get('name', 'Station')}): {lat}, {lon}")
            df = fetch_openmeteo_hourly(client, lat, lon, args.start, args.end, station_id=st_code)
            if not df.empty:
                frames.append(df)

    if not frames:
        sys.exit("No data returned from Open-Meteo API.")

    combined = pd.concat(frames, ignore_index=True)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_path, index=False)

    print(f"\nWrote {len(combined):,} hourly observation records to {out_path}")
    print("\nSample records:")
    print(combined.head(5)[["station_id", "timestamp", "temperature", "humidity", "pressure", "wind_speed"]])


if __name__ == "__main__":
    main()
