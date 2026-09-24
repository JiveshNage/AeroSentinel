"""
test_auth.py — Unit and Integration Tests for Authentication & Role-Based Access Control (F15)
Feature: F15 — Auth & roles (Phase 5 Stretch Goal)

1. Password hashing & constant-time verification.
2. JWT access token generation, decoding, expiry, and signature validation.
3. Login & profile introspection (/api/auth/login, /api/auth/me).
4. Role-gated route enforcement: verifies 403 Forbidden for unauthorized roles (Phase 5 exit criterion).
"""

from datetime import datetime, timezone, timedelta
import uuid
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from storage.base import Base
from storage.db import get_db
from storage.models import User, UserRole
from core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from main import app


@pytest.fixture
def memory_db():
    """Isolated in-memory SQLite database for testing authentication and RBAC."""
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
def seeded_users(memory_db):
    """Seed test users for each role."""
    users = {
        "admin": User(
            id=uuid.uuid4(),
            name="Admin User",
            email="admin@test.com",
            role=UserRole.admin,
            password_hash=hash_password("AdminPass123!"),
            created_at=datetime.now(timezone.utc),
        ),
        "dqo": User(
            id=uuid.uuid4(),
            name="DQO User",
            email="dqo@test.com",
            role=UserRole.data_quality_officer,
            password_hash=hash_password("DqoPass123!"),
            created_at=datetime.now(timezone.utc),
        ),
        "tech": User(
            id=uuid.uuid4(),
            name="Tech User",
            email="tech@test.com",
            role=UserRole.field_technician,
            password_hash=hash_password("TechPass123!"),
            created_at=datetime.now(timezone.utc),
        ),
        "forecaster": User(
            id=uuid.uuid4(),
            name="Forecaster User",
            email="forecaster@test.com",
            role=UserRole.forecaster,
            password_hash=hash_password("ForecasterPass123!"),
            created_at=datetime.now(timezone.utc),
        ),
    }
    for u in users.values():
        memory_db.add(u)
    memory_db.commit()
    return users


# ---------------------------------------------------------------------------
# 1. Password Hashing & Verification Tests
# ---------------------------------------------------------------------------

def test_password_hashing_and_verification():
    """Assert password hashing produces salted PBKDF2 hash and verifies correctly."""
    pw = "SecretTestingPassword123!"
    hashed = hash_password(pw)

    assert hashed.startswith("pbkdf2_sha256$100000$")
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(pw, "invalid_hash_string") is False


# ---------------------------------------------------------------------------
# 2. JWT Generation & Expiration Tests
# ---------------------------------------------------------------------------

def test_jwt_token_generation_and_decoding(seeded_users):
    """Assert JWT encodes claims and detects expiration."""
    user = seeded_users["admin"]
    token = create_access_token(user, expires_delta=timedelta(minutes=15))

    payload = decode_access_token(token)
    assert payload["sub"] == str(user.id)
    assert payload["email"] == user.email
    assert payload["role"] == "admin"
    assert payload["name"] == user.name

    # Expired token raises 401
    expired_token = create_access_token(user, expires_delta=timedelta(seconds=-10))
    with pytest.raises(Exception) as excinfo:
        decode_access_token(expired_token)
    assert "expired" in str(excinfo.value.detail).lower()

    # Tampered token raises 401
    tampered = token[:-4] + "abcd"
    with pytest.raises(Exception):
        decode_access_token(tampered)


# ---------------------------------------------------------------------------
# 3. Auth API Endpoints (Login & Introspection)
# ---------------------------------------------------------------------------

def test_auth_login_and_me_endpoints(memory_db, seeded_users):
    """Test POST /api/auth/login and GET /api/auth/me."""
    app.dependency_overrides[get_db] = lambda: memory_db
    client = TestClient(app)

    try:
        # 1. Valid login
        resp = client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "AdminPass123!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "admin@test.com"
        assert data["user"]["role"] == "admin"

        token = data["access_token"]

        # 2. GET /api/auth/me with valid Bearer token
        me_resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "admin@test.com"

        # 3. Invalid password
        bad_pw_resp = client.post(
            "/api/auth/login",
            json={"email": "admin@test.com", "password": "IncorrectPassword"},
        )
        assert bad_pw_resp.status_code == 401

        # 4. Unknown email
        unknown_resp = client.post(
            "/api/auth/login",
            json={"email": "unknown@test.com", "password": "AnyPassword"},
        )
        assert unknown_resp.status_code == 401

        # 5. GET /api/auth/me without token -> 401
        no_auth_resp = client.get("/api/auth/me")
        assert no_auth_resp.status_code == 401

    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. Role-Gated Route Enforcement (Phase 5 Exit Criterion: 403 on wrong role)
# ---------------------------------------------------------------------------

def test_role_gating_enforcement_403(memory_db, seeded_users):
    """
    PHASE 5 EXIT CRITERION:
    Role restrictions are verifiably enforced:
    - User with permitted role receives 200 OK.
    - User with wrong role receives 403 Forbidden.
    """
    app.dependency_overrides[get_db] = lambda: memory_db
    client = TestClient(app)

    try:
        admin_token = create_access_token(seeded_users["admin"])
        tech_token = create_access_token(seeded_users["tech"])
        forecaster_token = create_access_token(seeded_users["forecaster"])

        # 1. Admin accesses /api/auth/admin-only -> 200 OK
        resp_admin_on_admin = client.get(
            "/api/auth/admin-only",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp_admin_on_admin.status_code == 200
        assert resp_admin_on_admin.json()["role"] == "admin"

        # 2. Technician accesses /api/auth/tech-only -> 200 OK
        resp_tech_on_tech = client.get(
            "/api/auth/tech-only",
            headers={"Authorization": f"Bearer {tech_token}"},
        )
        assert resp_tech_on_tech.status_code == 200
        assert resp_tech_on_tech.json()["role"] == "field_technician"

        # 3. PHASE 5 EXIT CRITERION: Field Technician accesses /api/auth/admin-only -> 403 FORBIDDEN
        resp_tech_on_admin = client.get(
            "/api/auth/admin-only",
            headers={"Authorization": f"Bearer {tech_token}"},
        )
        assert resp_tech_on_admin.status_code == 403
        assert "forbidden" in resp_tech_on_admin.json()["detail"].lower()
        assert "field_technician" in resp_tech_on_admin.json()["detail"]

        # 4. Forecaster accesses /api/auth/tech-only -> 403 FORBIDDEN
        resp_forecaster_on_tech = client.get(
            "/api/auth/tech-only",
            headers={"Authorization": f"Bearer {forecaster_token}"},
        )
        assert resp_forecaster_on_tech.status_code == 403
        assert "forbidden" in resp_forecaster_on_tech.json()["detail"].lower()

        # 5. Unauthenticated request to protected endpoint -> 401 UNAUTHORIZED
        resp_unauth = client.get("/api/auth/admin-only")
        assert resp_unauth.status_code == 401

    finally:
        app.dependency_overrides.clear()
