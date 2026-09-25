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

DEFAULT_NCR_STATIONS = [
    {
        "station_code": "NCR001",
        "name": "Delhi (Safdarjung)",
        "latitude": 28.5822,
        "longitude": 77.2066,
        "elevation_m": 216.0,
        "state": "Delhi",
        "district": "New Delhi",
    },
    {
        "station_code": "NCR002",
        "name": "Gurugram",
        "latitude": 28.4595,
        "longitude": 77.0266,
        "elevation_m": 217.0,
        "state": "Haryana",
        "district": "Gurugram",
    },
    {
        "station_code": "NCR003",
        "name": "Noida",
        "latitude": 28.5355,
        "longitude": 77.3910,
        "elevation_m": 201.0,
        "state": "Uttar Pradesh",
        "district": "Gautam Buddh Nagar",
    },
    {
        "station_code": "NCR004",
        "name": "Faridabad",
        "latitude": 28.4089,
        "longitude": 77.3178,
        "elevation_m": 201.0,
        "state": "Haryana",
        "district": "Faridabad",
    },
    {
        "station_code": "NCR005",
        "name": "Ghaziabad",
        "latitude": 28.6692,
        "longitude": 77.4538,
        "elevation_m": 214.0,
        "state": "Uttar Pradesh",
        "district": "Ghaziabad",
    },
    {
        "station_code": "NCR006",
        "name": "Meerut",
        "latitude": 28.9845,
        "longitude": 77.7064,
        "elevation_m": 219.0,
        "state": "Uttar Pradesh",
        "district": "Meerut",
    },
    {
        "station_code": "NCR007",
        "name": "Rohtak",
        "latitude": 28.8955,
        "longitude": 76.6066,
        "elevation_m": 219.0,
        "state": "Haryana",
        "district": "Rohtak",
    },
    {
        "station_code": "NCR008",
        "name": "Panipat",
        "latitude": 29.3909,
        "longitude": 76.9635,
        "elevation_m": 219.0,
        "state": "Haryana",
        "district": "Panipat",
    },
    {
        "station_code": "NCR009",
        "name": "Bulandshahr",
        "latitude": 28.4041,
        "longitude": 77.8498,
        "elevation_m": 188.0,
        "state": "Uttar Pradesh",
        "district": "Bulandshahr",
    },
    {
        "station_code": "NCR010",
        "name": "Alwar",
        "latitude": 27.5530,
        "longitude": 76.6346,
        "elevation_m": 268.0,
        "state": "Rajasthan",
        "district": "Alwar",
    },
    {
        "station_code": "NCR011",
        "name": "Sonipat",
        "latitude": 28.9931,
        "longitude": 77.0151,
        "elevation_m": 220.0,
        "state": "Haryana",
        "district": "Sonipat",
    },
    {
        "station_code": "NCR012",
        "name": "Palwal",
        "latitude": 28.1447,
        "longitude": 77.3272,
        "elevation_m": 201.0,
        "state": "Haryana",
        "district": "Palwal",
    },
    {
        "station_code": "NCR013",
        "name": "Bharatpur",
        "latitude": 27.2152,
        "longitude": 77.4909,
        "elevation_m": 178.0,
        "state": "Rajasthan",
        "district": "Bharatpur",
    },
    {
        "station_code": "NCR014",
        "name": "Baghpat",
        "latitude": 28.9448,
        "longitude": 77.2183,
        "elevation_m": 225.0,
        "state": "Uttar Pradesh",
        "district": "Baghpat",
    },
    {
        "station_code": "NCR015",
        "name": "Jhajjar",
        "latitude": 28.6100,
        "longitude": 76.6565,
        "elevation_m": 220.0,
        "state": "Haryana",
        "district": "Jhajjar",
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
        storage_dir = Path(__file__).resolve().parent
        workspace_root = storage_dir.parent.parent
        csv_candidates = [
            storage_dir / "stations.csv",
            workspace_root / "Dataset" / "stations.csv",
            workspace_root / "data" / "stations.csv",
            storage_dir.parent / "data" / "stations.csv",
        ]
        csv_path = None
        for cand in csv_candidates:
            if cand.exists():
                csv_path = cand
                break

        stations_to_seed = []
        if csv_path:
            stations_to_seed.extend(load_stations_csv(csv_path))

        # Ensure all default NCR stations exist (guarantees NCR001-NCR015 even without CSV)
        existing_codes = {s["station_code"] for s in stations_to_seed}
        for ncr_default in DEFAULT_NCR_STATIONS:
            if ncr_default["station_code"] not in existing_codes:
                stations_to_seed.append(ncr_default)
                existing_codes.add(ncr_default["station_code"])

        # Add additional stations to ensure >= 20 stations
        for extra in ADDITIONAL_STATIONS:
            if extra["station_code"] not in existing_codes:
                stations_to_seed.append(extra)
                existing_codes.add(extra["station_code"])

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

        # 3. Seed RBAC roles, permissions, and accounts
        from core.auth import hash_password
        from core.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS_MAP
        from storage.models import Role, Permission, RolePermission, AuditLog, SystemSetting

        # A. Seed Permissions
        perm_objs = {}
        for code, (module_name, desc_text) in ALL_PERMISSIONS.items():
            existing_p = db.query(Permission).filter(Permission.code == code).first()
            if not existing_p:
                p = Permission(
                    id=uuid.uuid4(),
                    code=code,
                    module=module_name,
                    description=desc_text,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(p)
                perm_objs[code] = p
            else:
                perm_objs[code] = existing_p
        db.flush()

        # B. Seed Roles & Mappings
        role_definitions = [
            ("admin", "System Administrator", "Full uninhibited access to all application domains, governance, and ML models."),
            ("forecaster", "Operational Forecaster", "Meteorological analysis, severe weather warnings, anomalies, and active alerts."),
            ("qc_analyst", "Quality Control Analyst", "Sensor validation, anomaly adjudication, data upload, and QC false-alarm tuning."),
            ("data_quality_officer", "Data Quality Officer", "Legacy alias for QC Analyst."),
            ("field_technician", "Field Maintenance Technician", "Station sensor hardware status, preventative maintenance work orders, and field telemetry."),
            ("viewer", "Read-Only Observer", "Public / stakeholder read-only view of current station status, maps, and telemetry."),
        ]

        for r_name, d_name, r_desc in role_definitions:
            existing_r = db.query(Role).filter(Role.name == r_name).first()
            if not existing_r:
                r_obj = Role(
                    id=uuid.uuid4(),
                    name=r_name,
                    display_name=d_name,
                    description=r_desc,
                    is_system=True,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(r_obj)
                db.flush()
            else:
                r_obj = existing_r

            # Map permissions
            assigned_codes = ROLE_PERMISSIONS_MAP.get(r_name, [])
            for c in assigned_codes:
                p_item = perm_objs.get(c) or db.query(Permission).filter(Permission.code == c).first()
                if p_item:
                    existing_rp = db.query(RolePermission).filter(
                        RolePermission.role_id == r_obj.id,
                        RolePermission.permission_id == p_item.id,
                    ).first()
                    if not existing_rp:
                        db.add(RolePermission(role_id=r_obj.id, permission_id=p_item.id))
        db.flush()

        # C. Seed User Accounts for all 5 roles
        seed_users = [
            {
                "email": "admin@imd.gov.in",
                "name": "Dr. R. Sharma (System Administrator)",
                "role": UserRole.admin,
                "password": "AdminPassword123!",
            },
            {
                "email": "forecaster@imd.gov.in",
                "name": "P. Nair (Operational Forecaster)",
                "role": UserRole.forecaster,
                "password": "ForecasterPassword123!",
            },
            {
                "email": "qc@imd.gov.in",
                "name": "A. Verma (Quality Control Analyst)",
                "role": UserRole.qc_analyst,
                "password": "QcPassword123!",
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
                "email": "viewer@imd.gov.in",
                "name": "S. Das (Read-Only Observer)",
                "role": UserRole.viewer,
                "password": "ViewerPassword123!",
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
        db.flush()

        # D. Seed Initial Audit Logs
        if db.query(AuditLog).count() == 0:
            initial_logs = [
                ("admin@imd.gov.in", "system_boot", "kernel", {"status": "initialized", "version": "v2.4-PROD"}),
                ("admin@imd.gov.in", "rbac_synced", "permissions", {"total_permissions": len(ALL_PERMISSIONS)}),
                ("qc@imd.gov.in", "login", "auth", {"method": "bearer_jwt", "client": "operations_console"}),
                ("forecaster@imd.gov.in", "view_fleet", "fleet_map", {"cluster": "NCR_REGIONAL"}),
                ("tech@imd.gov.in", "inspect_station", "NCR007", {"status": "maintenance_scheduled"}),
            ]
            for email, act, res, det in initial_logs:
                db.add(AuditLog(
                    user_email=email,
                    action=act,
                    resource=res,
                    details=det,
                    ip_address="127.0.0.1",
                    created_at=datetime.now(timezone.utc),
                ))

        # E. Seed Default System Settings
        if db.query(SystemSetting).count() == 0:
            default_settings = [
                ("pipeline.isolation_forest.contamination", {"value": 0.05, "type": "float"}, "Contamination fraction parameter for unsupervised anomaly scoring"),
                ("pipeline.kdtree.neighbor_k", {"value": 5, "type": "int"}, "Number of nearest spatial neighbor AWS stations queried for consistency validation"),
                ("pipeline.retrain.auto_retrain_days", {"value": 7, "type": "int"}, "Automated background model retraining cycle interval"),
                ("notifications.critical_alert_sound", {"value": True, "type": "bool"}, "Play auditory alert in operations room for critical faults"),
                ("ingestion.rate_limit_per_min", {"value": 600, "type": "int"}, "Max HTTP ingestion telemetry requests accepted per AWS station node"),
            ]
            for k, v, d in default_settings:
                db.add(SystemSetting(
                    key=k,
                    value=v,
                    description=d,
                    updated_by="system",
                    updated_at=datetime.now(timezone.utc),
                ))
        db.commit()

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
