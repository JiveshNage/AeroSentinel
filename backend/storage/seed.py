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
        # Ensure schema tables exist
        Base.metadata.create_all(bind=engine)

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

        # 3. Seed RBAC role accounts for live demonstration
        from core.auth import hash_password
        seed_users = [
            {
                "email": "admin@imd.gov.in",
                "name": "Dr. R. Sharma (System Administrator)",
                "role": UserRole.admin,
                "password": "AdminPassword123!",
            },
            {
                "email": "operator@imd.gov.in",
                "name": "A. Verma (Data Quality Officer)",
                "role": UserRole.data_quality_officer,
                "password": "OperatorPassword123!",
            },
            {
                "email": "tech@imd.gov.in",
                "name": "K. Singh (Field Maintenance Technician)",
                "role": UserRole.field_technician,
                "password": "TechPassword123!",
            },
            {
                "email": "forecaster@imd.gov.in",
                "name": "P. Nair (Regional Forecaster)",
                "role": UserRole.forecaster,
                "password": "ForecasterPassword123!",
            },
        ]

        for u in seed_users:
            existing_user = db.query(User).filter(User.email == u["email"]).first()
            if existing_user:
                existing_user.name = u["name"]
                existing_user.role = u["role"]
                existing_user.password_hash = hash_password(u["password"])
            else:
                new_user = User(
                    id=uuid.uuid4(),
                    name=u["name"],
                    email=u["email"],
                    role=u["role"],
                    password_hash=hash_password(u["password"]),
                    created_at=datetime.now(timezone.utc),
                )
                db.add(new_user)

        # 4. Seed operational tasks partitioned by RBAC role
        from storage.models import SystemTask
        existing_tasks_count = db.query(SystemTask).count()
        if existing_tasks_count == 0:
            seed_tasks = [
                # Admin (Governance, fleet models, system config)
                {
                    "title": "Quarterly IsolationForest Model Drift Evaluation",
                    "description": "Evaluate recent telemetry distribution against baseline models and retrain temperature & pressure anomaly detectors.",
                    "assigned_role": "admin",
                    "priority": "high",
                    "status": "in_progress",
                    "category": "governance",
                    "station_code": "ALL",
                    "assigned_to_name": "Dr. R. Sharma",
                    "due_date": "2026-10-05",
                    "notes": "Verify F1-score improvement on synthetic fault benchmarks.",
                },
                {
                    "title": "Audit Ingestion Throughput & Redis Latency",
                    "description": "Inspect daily volume metrics, verify TimescaleDB compression policies, and audit API key usage across IMD gateways.",
                    "assigned_role": "admin",
                    "priority": "medium",
                    "status": "pending",
                    "category": "governance",
                    "station_code": "ALL",
                    "assigned_to_name": "Dr. R. Sharma",
                    "due_date": "2026-10-12",
                    "notes": "Ensure p99 ingestion latency remains under 50ms.",
                },
                # Data Quality Officer (QC Triage, anomaly verification, false alarms)
                {
                    "title": "Investigate Severe Temperature Spike (+48.2°C) on NCR001",
                    "description": "Examine step-change test failure on Safdarjung sensor. Cross-reference with neighboring stations NCR002 and NCR003.",
                    "assigned_role": "data_quality_officer",
                    "priority": "critical",
                    "status": "in_progress",
                    "category": "quality_control",
                    "station_code": "NCR001",
                    "assigned_to_name": "A. Verma",
                    "due_date": "2026-09-25",
                    "notes": "Suspected localized thermal pocket or direct radiation shielding displacement.",
                },
                {
                    "title": "Verify Spatial Discrepancy on NCR003 Noida Sensor",
                    "description": "3D KDTree spatial check flagged 4.1-sigma residual against surrounding regional cluster.",
                    "assigned_role": "data_quality_officer",
                    "priority": "high",
                    "status": "pending",
                    "category": "quality_control",
                    "station_code": "NCR003",
                    "assigned_to_name": "A. Verma",
                    "due_date": "2026-09-26",
                    "notes": "Compare with satellite thermal infrared band over Gautam Buddh Nagar.",
                },
                {
                    "title": "Triage Pressure Sensor Flatline Anomaly on NCR005",
                    "description": "Continuous 1012.4 hPa reading for 18 consecutive intervals. Verify sensor telemetry stream.",
                    "assigned_role": "data_quality_officer",
                    "priority": "high",
                    "status": "pending",
                    "category": "quality_control",
                    "station_code": "NCR005",
                    "assigned_to_name": "A. Verma",
                    "due_date": "2026-09-27",
                    "notes": "Likely analog-to-digital converter freeze or serial bus hang.",
                },
                # Field Technician (Hardware repair, sensor calibration, battery check)
                {
                    "title": "Emergency Battery & Solar Array Service on NCR010 Alwar",
                    "description": "Predictive maintenance model indicates 89% failure probability due to voltage degradation under cloudy conditions.",
                    "assigned_role": "field_technician",
                    "priority": "critical",
                    "status": "in_progress",
                    "category": "maintenance",
                    "station_code": "NCR010",
                    "assigned_to_name": "K. Singh",
                    "due_date": "2026-09-26",
                    "notes": "Carry replacement 12V 40Ah AGM deep-cycle battery and 50W photovoltaic panel.",
                },
                {
                    "title": "Recalibrate Ultrasonic Anemometer on NCR002 Gurugram",
                    "description": "Wind speed readings exhibiting high step-test variance after seasonal dust storm.",
                    "assigned_role": "field_technician",
                    "priority": "high",
                    "status": "pending",
                    "category": "maintenance",
                    "station_code": "NCR002",
                    "assigned_to_name": "K. Singh",
                    "due_date": "2026-09-28",
                    "notes": "Inspect acoustic transducers for grit accumulation and re-level mast mount.",
                },
                {
                    "title": "Pluviometer Funnel Silt Clearance on NCR012 Palwal",
                    "description": "Tipping bucket rain gauge reporting zero accumulation during recorded regional precipitation.",
                    "assigned_role": "field_technician",
                    "priority": "medium",
                    "status": "completed",
                    "category": "maintenance",
                    "station_code": "NCR012",
                    "assigned_to_name": "K. Singh",
                    "due_date": "2026-09-22",
                    "notes": "Cleaned organic debris from siphon orifice; calibrated tipping bucket mechanism.",
                },
                # Forecaster (Synoptic validation, severe weather advisory, cross-station trends)
                {
                    "title": "Synoptic Western Disturbance Squall Line Tracking",
                    "description": "Correlate barometric pressure drop gradients across western stations NCR007, NCR008, NCR010.",
                    "assigned_role": "forecaster",
                    "priority": "critical",
                    "status": "in_progress",
                    "category": "forecasting",
                    "station_code": "NCR007",
                    "assigned_to_name": "P. Nair",
                    "due_date": "2026-09-25",
                    "notes": "Prepare regional micro-climate advisory for Delhi NCR aviation corridor.",
                },
                {
                    "title": "Validate Regional Heatwave Gradient across Haryana Sector",
                    "description": "Review maximum 2-meter air temperature values against Doppler radar boundary layer estimates.",
                    "assigned_role": "forecaster",
                    "priority": "medium",
                    "status": "pending",
                    "category": "forecasting",
                    "station_code": "NCR011",
                    "assigned_to_name": "P. Nair",
                    "due_date": "2026-09-29",
                    "notes": "Verify heat index calculations for public weather bulletins.",
                },
            ]
            for t_data in seed_tasks:
                task = SystemTask(
                    id=uuid.uuid4(),
                    title=t_data["title"],
                    description=t_data["description"],
                    assigned_role=t_data["assigned_role"],
                    priority=t_data["priority"],
                    status=t_data["status"],
                    category=t_data["category"],
                    station_code=t_data.get("station_code"),
                    assigned_to_name=t_data.get("assigned_to_name"),
                    due_date=t_data.get("due_date"),
                    notes=t_data.get("notes"),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(task)

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
