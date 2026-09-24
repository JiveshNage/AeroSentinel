"""
test_maintenance.py — Unit and Integration Tests for Predictive Maintenance (F16)
Feature: F16 — Predictive Maintenance Scoring (Phase 5 Stretch Goal)

1. Feature extraction: distinguishes clean stations from degraded stations.
2. Ranking plausibility: degraded/failing stations rank strictly higher than clean stations (Phase 5 exit criterion).
3. Database persistence: validates records in maintenance_predictions table.
4. REST API: tests list, recompute, and detail endpoints.
"""

from datetime import datetime, timezone, timedelta, date
import uuid
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from storage.base import Base
from storage.db import get_db
from storage.models import (
    Station,
    RawReading,
    QCResult,
    QCVerdict,
    Alert,
    AlertSeverity,
    AlertStatus,
    StationStatus,
    MaintenancePrediction,
)
from main import app
from maintenance.service import (
    extract_station_health_features,
    calculate_failure_risk,
    recompute_fleet_predictions,
    get_ranked_predictions,
    get_station_maintenance_detail,
)


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database for testing predictive maintenance."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def populated_stations(memory_db):
    """Seed three stations: one healthy/clean, one moderately degraded, and one failing/critical."""
    now = datetime.now(timezone.utc)

    # 1. Clean nominal station
    st_clean = Station(
        id=uuid.uuid4(),
        station_code="DEL_CLEAN",
        name="Delhi Clean AWS",
        latitude=28.58,
        longitude=77.20,
        elevation_m=215.0,
        state="Delhi",
        district="New Delhi",
        install_date=date(2023, 1, 1),
        status=StationStatus.active,
    )

    # 2. Moderately degraded station (occasional suspect readings and 1 warning alert)
    st_mod = Station(
        id=uuid.uuid4(),
        station_code="DEL_MOD",
        name="Delhi Moderate AWS",
        latitude=28.60,
        longitude=77.22,
        elevation_m=220.0,
        state="Delhi",
        district="Central Delhi",
        install_date=date(2021, 6, 1),
        status=StationStatus.active,
    )

    # 3. Critical failing station (severe drift, flatlines, open critical alerts)
    st_crit = Station(
        id=uuid.uuid4(),
        station_code="DEL_CRIT",
        name="Delhi Failing AWS",
        latitude=28.65,
        longitude=77.18,
        elevation_m=210.0,
        state="Delhi",
        district="North Delhi",
        install_date=date(2019, 3, 1),
        status=StationStatus.active,
    )

    memory_db.add_all([st_clean, st_mod, st_crit])
    memory_db.commit()

    # Add readings for all 3 stations
    for st in [st_clean, st_mod, st_crit]:
        for i in range(20):
            ts = now - timedelta(hours=20 - i)
            r = RawReading(
                station_id=st.id,
                timestamp=ts,
                temperature=25.0 + (i * 0.1),
                humidity=50.0,
                pressure=1013.0,
                wind_speed=3.0,
                wind_direction=180.0,
                rainfall=0.0,
                solar_radiation=400.0,
            )
            memory_db.add(r)
            memory_db.flush()

            # Assign QC results based on station profile
            if st == st_clean:
                # 100% valid
                qc = QCResult(
                    reading_id=r.id,
                    station_id=st.id,
                    variable="temperature",
                    verdict=QCVerdict.valid,
                    reason_code="VALID",
                    confidence=1.0,
                )
                memory_db.add(qc)

            elif st == st_mod:
                # 2 suspect readings
                verdict = QCVerdict.suspect if i >= 18 else QCVerdict.valid
                reason = "ML_BORDERLINE" if i >= 18 else "VALID"
                qc = QCResult(
                    reading_id=r.id,
                    station_id=st.id,
                    variable="temperature",
                    verdict=verdict,
                    reason_code=reason,
                    confidence=0.65,
                )
                memory_db.add(qc)

            elif st == st_crit:
                # Severe persistent drift and flatlines
                if i >= 10:
                    verdict = QCVerdict.anomalous
                    fault = "drift" if i < 16 else "flatline"
                    reason = "ML_LSTM_AE" if fault == "drift" else "RULE_FLATLINE"
                else:
                    verdict = QCVerdict.valid
                    fault = None
                    reason = "VALID"
                qc = QCResult(
                    reading_id=r.id,
                    station_id=st.id,
                    variable="temperature",
                    verdict=verdict,
                    reason_code=reason,
                    fault_type=fault,
                    confidence=0.95,
                )
                memory_db.add(qc)

    # Add alert on st_mod
    a_mod = Alert(
        station_id=st_mod.id,
        qc_result_id=1,
        severity=AlertSeverity.medium,
        status=AlertStatus.open,
        message="Moderate temperature fluctuation",
    )
    memory_db.add(a_mod)

    # Add multiple critical alerts on st_crit
    a_crit1 = Alert(
        station_id=st_crit.id,
        qc_result_id=1,
        severity=AlertSeverity.critical,
        status=AlertStatus.open,
        message="Severe sensor drift detected",
    )
    a_crit2 = Alert(
        station_id=st_crit.id,
        qc_result_id=1,
        severity=AlertSeverity.critical,
        status=AlertStatus.open,
        message="Transducer flatline detected",
    )
    memory_db.add_all([a_crit1, a_crit2])
    memory_db.commit()

    return {"clean": st_clean, "mod": st_mod, "crit": st_crit}


# ---------------------------------------------------------------------------
# 1. Feature Extraction Tests
# ---------------------------------------------------------------------------

def test_feature_extraction_clean_vs_degraded(memory_db, populated_stations):
    """Verify feature extractor correctly distinguishes clean vs failing station metrics."""
    st_clean = populated_stations["clean"]
    st_crit = populated_stations["crit"]

    feat_clean = extract_station_health_features(memory_db, st_clean)
    feat_crit = extract_station_health_features(memory_db, st_crit)

    assert feat_clean["total_readings"] == 20
    assert feat_clean["anomalous_qc_count"] == 0
    assert feat_clean["anom_rate"] == 0.0
    assert feat_clean["drift_fault_count"] == 0
    assert feat_clean["open_alerts_count"] == 0

    assert feat_crit["total_readings"] == 20
    assert feat_crit["anomalous_qc_count"] == 10
    assert feat_crit["anom_rate"] == 0.50
    assert feat_crit["drift_fault_count"] == 6
    assert feat_crit["flatline_fault_count"] == 4
    assert feat_crit["critical_alerts_count"] == 2


# ---------------------------------------------------------------------------
# 2. Predictive Risk Scoring & Ranking Plausibility (Phase 5 Exit Criterion)
# ---------------------------------------------------------------------------

def test_predictive_risk_scoring_ranking_plausibility(memory_db, populated_stations):
    """
    PHASE 5 EXIT CRITERION:
    Ranked failure-risk list is plausible against historical fault patterns:
    stations that did experience anomalies/drift rank strictly higher in failure
    probability than clean stations.
    """
    st_clean = populated_stations["clean"]
    st_mod = populated_stations["mod"]
    st_crit = populated_stations["crit"]

    feat_clean = extract_station_health_features(memory_db, st_clean)
    feat_mod = extract_station_health_features(memory_db, st_mod)
    feat_crit = extract_station_health_features(memory_db, st_crit)

    p_clean, lvl_clean, top_clean, _, _ = calculate_failure_risk(feat_clean)
    p_mod, lvl_mod, top_mod, _, _ = calculate_failure_risk(feat_mod)
    p_crit, lvl_crit, top_crit, rec_crit, factors_crit = calculate_failure_risk(feat_crit)

    # 1. Monotonic ordering of risk probabilities: Clean < Moderate < Critical
    assert p_clean < p_mod < p_crit

    # 2. Risk levels
    assert lvl_clean == "nominal"
    assert lvl_crit == "critical"
    assert p_crit >= 0.70
    assert p_clean < 0.20

    # 3. Explainability & Diagnostics
    assert top_crit in ["Sensor Drift Accumulation", "High QC Anomaly Rate", "Sensor Flatline / Freeze"]
    assert "recalibration" in rec_crit.lower() or "maintenance" in rec_crit.lower() or "inspect" in rec_crit.lower()
    assert "factor_breakdown" in factors_crit


# ---------------------------------------------------------------------------
# 3. Fleet Recompute & Database Persistence
# ---------------------------------------------------------------------------

def test_maintenance_predictions_db_persistence(memory_db, populated_stations):
    """Verify fleet recomputation creates and queries records in maintenance_predictions."""
    ranked = recompute_fleet_predictions(memory_db)

    assert len(ranked) == 3
    # Top station must be DEL_CRIT
    assert ranked[0].station_code == "DEL_CRIT"
    assert ranked[0].risk_level == "critical"
    # Bottom station must be DEL_CLEAN
    assert ranked[-1].station_code == "DEL_CLEAN"
    assert ranked[-1].risk_level == "nominal"

    # Verify query summary
    summary = get_ranked_predictions(memory_db)
    assert summary.total_stations == 3
    assert summary.critical_risk_count == 1
    assert summary.nominal_risk_count == 1
    assert 0.0 < summary.mean_failure_probability < 1.0


# ---------------------------------------------------------------------------
# 4. REST API Integration
# ---------------------------------------------------------------------------

def test_maintenance_rest_api_lifecycle(memory_db, populated_stations):
    """Test REST API endpoints for predictive maintenance."""
    app.dependency_overrides[get_db] = lambda: memory_db
    client = TestClient(app)

    try:
        # 1. GET /api/maintenance/predictions
        resp = client.get("/api/maintenance/predictions")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_stations" in data
        assert "ranked_predictions" in data
        assert len(data["ranked_predictions"]) == 3
        # First entry is highest risk
        assert data["ranked_predictions"][0]["failure_probability_30d"] >= data["ranked_predictions"][-1]["failure_probability_30d"]

        # 2. Filter by risk_level=critical
        resp_filtered = client.get("/api/maintenance/predictions?risk_level=critical")
        assert resp_filtered.status_code == 200
        filtered_data = resp_filtered.json()
        assert len(filtered_data["ranked_predictions"]) == 1
        assert filtered_data["ranked_predictions"][0]["station_code"] == "DEL_CRIT"

        # 3. POST /api/maintenance/recompute
        resp_recompute = client.post("/api/maintenance/recompute")
        assert resp_recompute.status_code == 200
        assert len(resp_recompute.json()["ranked_predictions"]) == 3

        # 4. GET /api/maintenance/stations/{station_id}
        st_id = str(populated_stations["crit"].id)
        resp_st = client.get(f"/api/maintenance/stations/{st_id}")
        assert resp_st.status_code == 200
        st_data = resp_st.json()
        assert st_data["station_code"] == "DEL_CRIT"
        assert st_data["risk_level"] == "critical"
        assert "factor_breakdown" in st_data["top_factors"]

        # 5. Error handling
        resp_bad_uuid = client.get("/api/maintenance/stations/not-a-valid-uuid")
        assert resp_bad_uuid.status_code == 400

        resp_not_found = client.get(f"/api/maintenance/stations/{uuid.uuid4()}")
        assert resp_not_found.status_code == 404

    finally:
        app.dependency_overrides.clear()
