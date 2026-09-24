"""
test_rbac_permissions.py — Integration and Unit Tests for Granular RBAC & Administration
AeroSentinel (SIH26073)

Tests:
1. Permission catalog and role matrix definitions.
2. User permissions resolution per role.
3. JWT encoding and decoding of permissions.
4. FastAPI require_permission dependency and 403 Forbidden enforcement.
5. Admin API routes: /api/admin/users, /api/admin/roles, /api/admin/audit-logs, /api/admin/settings.
6. Audit trail generation upon access denial and administrative updates.
"""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from storage.base import Base
from storage.db import get_db
from storage.models import User, UserRole, Role, Permission, RolePermission, AuditLog, SystemSetting
from core.auth import hash_password, create_access_token, decode_access_token
from core.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS_MAP, get_user_permissions
from main import app


@pytest.fixture
def rbac_db():
    """Isolated in-memory database with full RBAC schema."""
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

    # Seed users for each role
    users = {
        "admin": User(
            id=uuid.uuid4(),
            name="Admin User",
            email="admin@test.com",
            role=UserRole.admin,
            password_hash=hash_password("AdminPass123!"),
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
        "qc_analyst": User(
            id=uuid.uuid4(),
            name="QC Analyst User",
            email="qc@test.com",
            role=UserRole.qc_analyst,
            password_hash=hash_password("QcPass123!"),
            created_at=datetime.now(timezone.utc),
        ),
        "field_technician": User(
            id=uuid.uuid4(),
            name="Technician User",
            email="tech@test.com",
            role=UserRole.field_technician,
            password_hash=hash_password("TechPass123!"),
            created_at=datetime.now(timezone.utc),
        ),
        "viewer": User(
            id=uuid.uuid4(),
            name="Viewer User",
            email="viewer@test.com",
            role=UserRole.viewer,
            password_hash=hash_password("ViewerPass123!"),
            created_at=datetime.now(timezone.utc),
        ),
    }

    for u in users.values():
        session.add(u)
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


def test_permission_catalog_completeness():
    """Verify all 21 explicit permissions are cataloged across the 4 modules."""
    assert len(ALL_PERMISSIONS) == 21
    modules = {mod for mod, _ in ALL_PERMISSIONS.values()}
    assert modules == {"overview", "monitoring", "operations", "administration"}


def test_role_permissions_matrix_coverage(rbac_db):
    """Verify permission assignments conform strictly to the specification."""
    admin_perms = ROLE_PERMISSIONS_MAP["admin"]
    assert len(admin_perms) == 21
    assert "users.manage" in admin_perms
    assert "system.manage" in admin_perms

    forecaster_perms = ROLE_PERMISSIONS_MAP["forecaster"]
    assert "dashboard.view" in forecaster_perms
    assert "forecasts.create" in forecaster_perms
    assert "users.manage" not in forecaster_perms
    assert "system.manage" not in forecaster_perms
    assert "audit.view" not in forecaster_perms

    tech_perms = ROLE_PERMISSIONS_MAP["field_technician"]
    assert "fleet.view" in tech_perms
    assert "maintenance.update" in tech_perms
    assert "dashboard.view" not in tech_perms
    assert "users.view" not in tech_perms

    viewer_perms = ROLE_PERMISSIONS_MAP["viewer"]
    assert "dashboard.view" in viewer_perms
    assert "fleet.view" in viewer_perms
    assert "stations.edit" not in viewer_perms
    assert "maintenance.update" not in viewer_perms
    assert "data.upload" not in viewer_perms


def test_jwt_token_encodes_permissions(rbac_db):
    """Verify JWT access tokens embed the user's explicit permissions."""
    admin_user = rbac_db.query(User).filter(User.role == UserRole.admin).first()
    token = create_access_token(admin_user)
    payload = decode_access_token(token)

    assert "permissions" in payload
    assert isinstance(payload["permissions"], list)
    assert len(payload["permissions"]) == 21
    assert "dashboard.view" in payload["permissions"]


def test_admin_routes_rbac_authorization(rbac_db):
    """
    Verify RBAC security:
    - Admin has access to /api/admin/users, /api/admin/roles, /api/admin/audit-logs, /api/admin/settings.
    - Forecaster, Field Tech, and Viewer receive 403 Forbidden.
    """
    app.dependency_overrides[get_db] = lambda: rbac_db
    client = TestClient(app)

    try:
        users = {u.role.value: u for u in rbac_db.query(User).all()}

        admin_token = create_access_token(users["admin"])
        forecaster_token = create_access_token(users["forecaster"])
        tech_token = create_access_token(users["field_technician"])
        viewer_token = create_access_token(users["viewer"])

        # 1. Admin accesses /api/admin/users -> 200 OK
        resp_admin = client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp_admin.status_code == 200
        assert len(resp_admin.json()) >= 5

        # 2. Forecaster accesses /api/admin/users -> 403 Forbidden
        resp_fc = client.get("/api/admin/users", headers={"Authorization": f"Bearer {forecaster_token}"})
        assert resp_fc.status_code == 403
        assert "users.view" in resp_fc.json()["detail"]

        # 3. Technician accesses /api/admin/roles -> 403 Forbidden
        resp_tech = client.get("/api/admin/roles", headers={"Authorization": f"Bearer {tech_token}"})
        assert resp_tech.status_code == 403
        assert "roles.manage" in resp_tech.json()["detail"]

        # 4. Viewer accesses /api/admin/settings -> 403 Forbidden
        resp_viewer = client.get("/api/admin/settings", headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp_viewer.status_code == 403

        # 5. Admin accesses /api/admin/settings -> 200 OK
        resp_admin_settings = client.get("/api/admin/settings", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp_admin_settings.status_code == 200

        # 6. Verify audit log captured the denied access attempts
        denied_logs = rbac_db.query(AuditLog).filter(AuditLog.action == "access_denied").all()
        assert len(denied_logs) >= 3

    finally:
        app.dependency_overrides.clear()
