#!/usr/bin/env python3
"""
seed_demo_state.py — Pre-Seeded Instant Demonstration State (F17 / Phase 6)

Pre-populates the database with a rich, realistic, interactive demonstration state:
1. Seeds 20 Indian AWS stations and 4 RBAC role accounts (Admin, DQO, Tech, Forecaster).
2. Generates 48 hours of multi-station telemetry.
3. Injects realistic faults (flatline on NCR003, spike on NCR002, drift on NCR004).
4. Executes the complete 4-tier QC pipeline, creating live operational alerts.
5. Populates operator feedback in the retraining pool.
6. Computes fleet-wide 30-day predictive maintenance risk rankings.

Usage:
    python scripts/seed_demo_state.py
"""

from datetime import datetime, timezone, timedelta
import logging
from pathlib import Path
import sys
import uuid

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from storage.db import SessionLocal
from storage.models import (
    Station,
    RawReading,
    QCResult,
    QCVerdict,
    Alert,
    AlertStatus,
    AlertSeverity,
    Feedback,
    FeedbackLabel,
    User,
    UserRole,
    StationStatus,
)
from storage.seed import seed_database
from ingestion.simulator import generate_synthetic_weather_stream
from qc.fault_injector import inject_flatline, inject_spike, inject_drift
from qc.classifier import run_full_qc_pipeline_for_reading
from maintenance.service import recompute_fleet_predictions

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_demo_state")


def seed_demo_environment():
    logger.info("==================================================================")
    logger.info("AeroSentinel: Seeding Instant Hackathon Demonstration State")
    logger.info("==================================================================")

    # 1. Seed base stations and RBAC users
    logger.info("[1/6] Seeding 20 IMD Automatic Weather Stations & RBAC accounts...")
    seed_database()

    db = SessionLocal()
    try:
        stations = db.query(Station).all()
        logger.info(f"Loaded {len(stations)} stations from registry.")

        # 2. Generate 48 hours of baseline multi-station synthetic weather data
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=48)
        logger.info(f"[2/6] Generating 48 hours of multi-station weather telemetry...")
        clean_df = generate_synthetic_weather_stream(stations, start_time=start_time, hours=48)

        # 3. Inject realistic faults into stream
        logger.info("[3/6] Injecting realistic sensor faults for live demonstration...")
        df_faults = clean_df.copy()

        # Fault A: Frozen temperature transducer (flatline) on NCR003 (Gurugram) for last 12 hours
        st_flatline = "NCR003"
        df_faults = inject_flatline(
            df_faults,
            variable="temperature",
            station_id=st_flatline,
            start_idx=36,
            duration=13,
            freeze_value=34.2,
        )

        # Fault B: Severe humidity sensor spike on NCR002 (Faridabad)
        st_spike = "NCR002"
        df_faults = inject_spike(
            df_faults,
            variable="humidity",
            station_id=st_spike,
            idx=42,
            magnitude=-45.0,
        )

        # Fault C: Monotonic sensor calibration drift on NCR004 (Noida)
        st_drift = "NCR004"
        df_faults = inject_drift(
            df_faults,
            variable="temperature",
            station_id=st_drift,
            start_idx=20,
            duration=28,
            total_drift=8.5,
        )

        # 4. Ingest telemetry into raw_readings table
        logger.info(f"[4/6] Persisting {len(df_faults)} readings to database...")
        station_map = {s.station_code: s for s in stations}
        inserted_readings = []

        # Sort chronologically to preserve real-world causality
        df_sorted = df_faults.sort_values("timestamp")

        # Clear existing readings for a clean demo state
        db.query(Alert).delete()
        db.query(Feedback).delete()
        db.query(QCResult).delete()
        db.query(RawReading).delete()
        db.commit()

        for _, row in df_sorted.iterrows():
            st_obj = station_map.get(row["station_id"])
            if not st_obj:
                continue

            ts_val = row["timestamp"]
            if hasattr(ts_val, "to_pydatetime"):
                py_dt = ts_val.to_pydatetime()
            elif isinstance(ts_val, str):
                py_dt = datetime.fromisoformat(ts_val)
            else:
                py_dt = ts_val

            if py_dt.tzinfo is None:
                py_dt = py_dt.replace(tzinfo=timezone.utc)

            r = RawReading(
                station_id=st_obj.id,
                timestamp=py_dt,
                temperature=row.get("temperature"),
                humidity=row.get("humidity"),
                pressure=row.get("pressure"),
                wind_speed=row.get("wind_speed"),
                wind_direction=row.get("wind_direction"),
                rainfall=row.get("rainfall"),
                solar_radiation=row.get("solar_radiation"),
            )
            db.add(r)
            inserted_readings.append(r)

        db.commit()

        # 5. Execute 4-Tier QC Pipeline on recent window to generate verdicts and live alerts
        logger.info("[5/6] Executing 4-Tier QC pipeline on recent telemetry window...")

        def to_utc(dt):
            if dt is None:
                return None
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

        recent_cutoff = now - timedelta(hours=3)
        recent_readings = [r for r in inserted_readings if to_utc(r.timestamp) >= recent_cutoff]

        qc_count = 0
        for r in recent_readings:
            qc_results = run_full_qc_pipeline_for_reading(db, r.id)
            qc_count += len(qc_results)

        total_alerts = db.query(Alert).count()
        logger.info(f"Generated {qc_count} QC verdicts and {total_alerts} operational alerts.")

        # Seed realistic operator feedback for the retraining console
        dqo_user = db.query(User).filter(User.role == UserRole.data_quality_officer).first()
        anom_qc = db.query(QCResult).filter(QCResult.verdict == QCVerdict.anomalous).limit(4).all()

        for i, q in enumerate(anom_qc):
            # Seed 2 confirmed faults and 2 false alarms
            label = FeedbackLabel.confirmed_fault if i % 2 == 0 else FeedbackLabel.false_alarm
            fb = Feedback(
                qc_result_id=q.id,
                user_id=dqo_user.id if dqo_user else None,
                label=label,
                notes="Verified during ground-truth sensor inspection." if label == FeedbackLabel.confirmed_fault else "Localized microclimate turbulence; not a sensor failure.",
                created_at=now - timedelta(hours=2 - i),
            )
            db.add(fb)
        db.commit()

        # 6. Compute 30-Day Predictive Maintenance Rankings
        logger.info("[6/6] Computing fleet predictive maintenance rankings...")
        recompute_fleet_predictions(db)

        # Summary Log
        top_alerts = db.query(Alert).filter(Alert.status == AlertStatus.open).limit(3).all()
        logger.info("==================================================================")
        logger.info("DEMO STATE SEEDING COMPLETE!")
        logger.info("==================================================================")
        logger.info(f"  • Active Stations: {len(stations)}")
        logger.info(f"  • Ingested Observations: {len(inserted_readings)}")
        logger.info(f"  • Open Alerts: {total_alerts}")
        logger.info(f"  • Top Open Alert: {top_alerts[0].message if top_alerts else 'None'}")
        logger.info("  • Ready for live evaluation at: http://localhost:5173")
        logger.info("==================================================================")

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding demo state: {e}", exc_info=True)
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_environment()
