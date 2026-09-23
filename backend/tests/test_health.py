from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient


def test_health_check_success(client: TestClient):
    """Happy path: GET /api/health returns 200 and expected schema."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "AeroSentinel"
    assert "version" in data
    assert "environment" in data
    assert "timestamp" in data
    assert "services" in data
    assert "fastapi" in data["services"]


def test_health_check_utc_timestamp(client: TestClient):
    """Data integrity: Server timestamp must be valid ISO 8601 and timezone-aware UTC."""
    response = client.get("/api/health")
    assert response.status_code == 200

    ts_str = response.json()["timestamp"]
    parsed_dt = datetime.fromisoformat(ts_str)
    assert parsed_dt.tzinfo is not None, "Timestamp must be timezone-aware"
    # Ensure timezone offset is UTC (+00:00)
    assert parsed_dt.utcoffset() == timezone.utc.utcoffset(None)


def test_root_endpoint_metadata(client: TestClient):
    """GET / returns valid application metadata links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "AeroSentinel"
    assert data["health"] == "/api/health"


def test_adversarial_method_not_allowed(client: TestClient):
    """Adversarial case: Calling POST /api/health should be rejected with 405."""
    response = client.post("/api/health", json={"malicious": "payload"})
    assert response.status_code == 405


def test_adversarial_nonexistent_endpoint(client: TestClient):
    """Adversarial case: Requesting an unknown endpoint returns 404."""
    response = client.get("/api/unknown_route")
    assert response.status_code == 404
