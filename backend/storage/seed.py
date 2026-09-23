import csv
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
import uuid

# Add backend directory to sys.path so imports work regardless of cwd
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session

from storage.db import SessionLocal, engine
from storage.base import Base
from storage.models import Station, StationStatus, User, UserRole

DEFAULT_SENSOR_SPECS = {
    "temperature": {"min": -10.0, "max": 55.0, "step_max": 8.0, "unit": "°C"},
    "humidity": {"min": 0.0, "max": 100.0, "step_max": 30.0, "unit": "%"},
    "pressure": {"min": 850.0, "max": 1080.0, "step_max": 15.0, "unit": "hPa"},
    "wind_speed": {"min": 0.0, "max": 65.0, "step_max": 20.0, "unit": "m/s"},
    "wind_direction": {"min": 0.0, "max": 360.0, "step_max": 180.0, "unit": "degrees"},
    "rainfall": {"min": 0.0, "max": 300.0, "step_max": 100.0, "unit": "mm"},
    "solar_radiation": {"min": 0.0, "max": 1500.0, "step_max": 500.0, "unit": "W/m²"},
}

ADDITIONAL_STATIONS = [
    {
        "station_code": "IND016",
        "name": "Mumbai (Colaba)",
        "latitude": 18.9067,
        "longitude": 72.8147,
        "elevation_m": 11.0,
        "state": "Maharashtra",
        "district": "Mumbai City",
    },
    {
        "station_code": "IND017",
        "name": "Chennai (Meenambakkam)",
        "latitude": 12.9941,
        "longitude": 80.1809,
        "elevation_m": 16.0,
        "state": "Tamil Nadu",
        "district": "Chennai",
    },
    {
        "station_code": "IND018",
        "name": "Kolkata (Alipore)",
        "latitude": 22.5326,
        "longitude": 88.3248,
        "elevation_m": 6.0,
        "state": "West Bengal",
        "district": "Kolkata",
    },
    {
        "station_code": "IND019",
        "name": "Bengaluru (HAL)",
        "latitude": 12.9553,
        "longitude": 77.6682,
        "elevation_m": 888.0,
        "state": "Karnataka",
        "district": "Bengaluru Urban",
    },
    {
        "station_code": "IND020",
        "name": "Shimla",
        "latitude": 31.1048,
        "longitude": 77.1734,
        "elevation_m": 2202.0,
        "state": "Himachal Pradesh",
        "district": "Shimla",
    },
]


def load_stations_csv(csv_path: Path) -> List[Dict[str, Any]]:
    stations = []
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stations.append({
                    "station_code": row["station_code"],
                    "name": row["name"],
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "elevation_m": float(row["elevation_m"]) if row.get("elevation_m") else None,
                    "state": row["state"],
                    "district": row["district"],
                })
    return stations


def seed_database(db: Session = None) -> int:
    """Idempotently seed the stations table and default users."""
    close_after = False
    if db is None:
        db = SessionLocal()
        close_after = True

    try:
        # 1. Locate stations.csv
        workspace_root = Path(__file__).resolve().parent.parent.parent
        csv_candidates = [
            workspace_root / "Dataset" / "stations.csv",
            workspace_root / "data" / "stations.csv",
        ]
        csv_path = None
        for cand in csv_candidates:
            if cand.exists():
                csv_path = cand
                break

        stations_to_seed = []
        if csv_path:
            stations_to_seed.extend(load_stations_csv(csv_path))

        # Add additional stations to ensure >= 20 stations
        existing_codes = {s["station_code"] for s in stations_to_seed}
        for extra in ADDITIONAL_STATIONS:
            if extra["station_code"] not in existing_codes:
                stations_to_seed.append(extra)

        # 2. Insert or update stations
        seeded_count = 0
        for item in stations_to_seed:
            existing = db.query(Station).filter(Station.station_code == item["station_code"]).first()
            if existing:
                existing.name = item["name"]
                existing.latitude = item["latitude"]
                existing.longitude = item["longitude"]
                existing.elevation_m = item["elevation_m"]
                existing.state = item["state"]
                existing.district = item["district"]
                existing.sensor_specs = DEFAULT_SENSOR_SPECS
                existing.status = StationStatus.active
            else:
                station = Station(
                    station_code=item["station_code"],
                    name=item["name"],
                    latitude=item["latitude"],
                    longitude=item["longitude"],
                    elevation_m=item["elevation_m"],
                    state=item["state"],
                    district=item["district"],
                    install_date=date(2021, 1, 15),
                    sensor_specs=DEFAULT_SENSOR_SPECS,
                    status=StationStatus.active,
                )
                db.add(station)
                seeded_count += 1

        # 3. Seed default operator user if not exists
        default_user = db.query(User).filter(User.email == "operator@imd.gov.in").first()
        if not default_user:
            admin_user = User(
                name="IMD Data Quality Officer",
                email="operator@imd.gov.in",
                role=UserRole.data_quality_officer,
                password_hash="pbkdf2_sha256$placeholder_hash",
            )
            db.add(admin_user)

        db.commit()
        return len(stations_to_seed)
    except Exception as e:
        db.rollback()
        raise e
    finally:
        if close_after:
            db.close()


if __name__ == "__main__":
    count = seed_database()
    print(f"Successfully seeded {count} stations.")
