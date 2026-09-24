"""
test_tasks_and_upload.py — Integration Tests for RBAC Task Division, File Upload, and Live Ticks
"""

import io
import pytest
from fastapi.testclient import TestClient


def test_list_tasks(client: TestClient):
    """Verify operational tasks list and count aggregation."""
    res = client.get("/api/tasks")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "tasks" in data
    assert data["total"] >= 1
    assert data["pending_count"] >= 0
    assert data["in_progress_count"] >= 0


def test_filter_tasks_by_role(client: TestClient):
    """Verify tasks are strictly partitioned by assigned RBAC roles."""
    roles = ["admin", "data_quality_officer", "field_technician", "forecaster"]
    for r in roles:
        res = client.get(f"/api/tasks?role={r}")
        assert res.status_code == 200
        data = res.json()
        for t in data["tasks"]:
            assert t["assigned_role"] == r


def test_create_and_update_task_lifecycle(client: TestClient):
    """Verify task creation, progression, and state transition."""
    # 1. Create task
    payload = {
        "title": "Calibrate NCR001 Pyranometer Sensor",
        "description": "Quarterly calibration check against reference secondary standard radiometer.",
        "assigned_role": "field_technician",
        "priority": "high",
        "status": "pending",
        "station_code": "NCR001",
        "assigned_to_name": "K. Singh",
        "due_date": "2026-10-15",
    }
    create_res = client.post("/api/tasks", json=payload)
    assert create_res.status_code == 201
    task_id = create_res.json()["id"]

    # 2. Update to in_progress
    patch_res = client.patch(f"/api/tasks/{task_id}", json={"status": "in_progress", "notes": "Technician on-site"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "in_progress"
    assert patch_res.json()["notes"] == "Technician on-site"

    # 3. Update to completed
    comp_res = client.patch(f"/api/tasks/{task_id}", json={"status": "completed"})
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "completed"

    # 4. Clean up
    del_res = client.delete(f"/api/tasks/{task_id}")
    assert del_res.status_code == 204


def test_upload_file_csv(client: TestClient):
    """Verify tabular CSV file ingestion and multi-tier QC execution."""
    csv_content = (
        "station_code,timestamp,temperature,humidity,pressure,wind_speed\n"
        "NCR001,2026-09-24T18:00:00Z,31.2,68.0,1012.0,3.5\n"
        "NCR002,2026-09-24T18:00:00Z,30.8,70.2,1012.4,3.2\n"
    )
    res = client.post(
        "/ingest/upload-file",
        files={"file": ("test_weather_data.csv", csv_content.encode("utf-8"), "text/csv")},
        data={"default_station_code": "NCR001"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "success"
    assert data["total_rows"] == 2
    assert "ingested_count" in data
    assert "duplicates_skipped" in data
    assert "anomalies_detected" in data
    assert isinstance(data["preview"], list)


def test_sample_template_download(client: TestClient):
    """Verify downloadable CSV template route."""
    res = client.get("/ingest/template.csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "station_code,timestamp,temperature" in res.text


def test_simulate_station_tick(client: TestClient):
    """Verify live telemetry tick simulation with normal and forced anomaly points."""
    # 1. Normal tick
    res_normal = client.post("/api/stations/NCR001/simulate-tick", json={"force_anomaly": False})
    assert res_normal.status_code == 200
    data_normal = res_normal.json()
    assert "temperature" in data_normal
    assert "qc_verdicts" in data_normal

    # 2. Forced anomaly spike
    res_spike = client.post(
        "/api/stations/NCR001/simulate-tick",
        json={"force_anomaly": True, "variable": "temperature", "fault_type": "spike"},
    )
    assert res_spike.status_code == 200
    data_spike = res_spike.json()
    assert data_spike["temperature"] is not None
    # Check that temperature QC detected the spike
    temp_qc = data_spike["qc_verdicts"].get("temperature", {})
    assert temp_qc.get("verdict") in ("anomalous", "suspect")
