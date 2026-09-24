"""
admin.py — Administration REST Endpoints (RBAC Governance, Audit, Settings)
AeroSentinel (SIH26073)

Endpoints:
- GET  /api/admin/users: List registered personnel (users.view)
- POST /api/admin/users: Create user account (users.manage)
- PUT  /api/admin/users/{id}: Update user role / status (users.manage)
- GET  /api/admin/roles: List all roles and assigned permissions (roles.manage)
- GET  /api/admin/permissions: List full permission catalog (roles.manage)
- GET  /api/admin/audit-logs: Security & operational audit trail (audit.view)
- GET  /api/admin/settings: Pipeline & model configuration (system.manage)
- POST /api/admin/settings: Update operational configuration (system.manage)
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from storage.db import get_db
from storage.models import User, UserRole, AuditLog, SystemSetting, Role, Permission
from core.auth import hash_password, get_current_user
from core.permissions import require_permission, ALL_PERMISSIONS, ROLE_PERMISSIONS_MAP, log_audit

router = APIRouter(prefix="/admin", tags=["Administration & Governance"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class AdminUserItem(BaseModel):
    id: str
    name: str
    email: str
    role: str
    created_at: datetime


class AdminUserCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    role: str = Field(..., description="admin, forecaster, qc_analyst, field_technician, viewer")


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None


class RoleInfo(BaseModel):
    name: str
    display_name: str
    description: str
    user_count: int
    permissions: List[str]


class PermissionInfo(BaseModel):
    code: str
    module: str
    description: str


class AuditLogItem(BaseModel):
    id: int
    user_email: str
    action: str
    resource: str
    details: Dict[str, Any]
    ip_address: Optional[str]
    created_at: datetime


class SettingItem(BaseModel):
    key: str
    value: Dict[str, Any]
    description: Optional[str]
    updated_by: Optional[str]
    updated_at: datetime


class SettingUpdate(BaseModel):
    key: str
    value: Dict[str, Any]
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# 1. User Management (users.view / users.manage)
# ---------------------------------------------------------------------------
@router.get("/users", response_model=List[AdminUserItem])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.view")),
):
    """List all registered system operators and user accounts."""
    users = db.query(User).order_by(User.name.asc()).all()
    return [
        AdminUserItem(
            id=str(u.id),
            name=u.name,
            email=u.email,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/users", response_model=AdminUserItem, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """Create a new operator account with explicit role assignment."""
    existing = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=409, detail="A user with this email address already exists.")

    try:
        role_enum = UserRole(payload.role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{payload.role}'. Must be one of: {list(ROLE_PERMISSIONS_MAP.keys())}",
        )

    new_user = User(
        id=uuid.uuid4(),
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        role=role_enum,
        password_hash=hash_password(payload.password),
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit(
        db=db,
        action="user_created",
        resource="users",
        user=current_user,
        details={"created_user_id": str(new_user.id), "email": new_user.email, "role": payload.role},
    )

    return AdminUserItem(
        id=str(new_user.id),
        name=new_user.name,
        email=new_user.email,
        role=new_user.role.value if hasattr(new_user.role, "value") else str(new_user.role),
        created_at=new_user.created_at,
    )


@router.put("/users/{user_id}", response_model=AdminUserItem)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """Update role or details for an existing user account."""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format.")

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.role is not None:
        try:
            user.role = UserRole(payload.role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role '{payload.role}'.")
    if payload.password is not None and len(payload.password) >= 6:
        user.password_hash = hash_password(payload.password)

    db.commit()
    db.refresh(user)

    log_audit(
        db=db,
        action="user_updated",
        resource="users",
        user=current_user,
        details={"updated_user_id": str(user.id), "email": user.email, "role": str(user.role)},
    )

    return AdminUserItem(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        created_at=user.created_at,
    )


# ---------------------------------------------------------------------------
# 2. Roles & Permissions Catalog (roles.manage)
# ---------------------------------------------------------------------------
@router.get("/roles", response_model=List[RoleInfo])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles.manage")),
):
    """Inspect all system roles and their assigned permission lists."""
    role_meta = {
        "admin": ("System Administrator", "Full uninhibited access to all application domains, governance, and ML models."),
        "forecaster": ("Operational Forecaster", "Meteorological analysis, severe weather warnings, anomalies, and active alerts."),
        "qc_analyst": ("Quality Control Analyst", "Sensor validation, anomaly adjudication, data upload, and QC false-alarm tuning."),
        "field_technician": ("Field Maintenance Technician", "Station sensor hardware status, preventative maintenance work orders, and field telemetry."),
        "viewer": ("Read-Only Observer", "Public / stakeholder read-only view of current station status, maps, and telemetry."),
    }

    result = []
    for r_name, perms in ROLE_PERMISSIONS_MAP.items():
        if r_name == "data_quality_officer":
            continue  # alias for qc_analyst
        display_name, desc_text = role_meta.get(r_name, (r_name.title(), "System Role"))
        count = db.query(User).filter(User.role == UserRole(r_name)).count()
        result.append(
            RoleInfo(
                name=r_name,
                display_name=display_name,
                description=desc_text,
                user_count=count,
                permissions=perms,
            )
        )
    return result


@router.get("/permissions", response_model=List[PermissionInfo])
def list_permissions(
    current_user: User = Depends(require_permission("roles.manage")),
):
    """List the full 21 explicit permissions partitioned by module domain."""
    return [
        PermissionInfo(code=code, module=mod, description=desc_text)
        for code, (mod, desc_text) in ALL_PERMISSIONS.items()
    ]


# ---------------------------------------------------------------------------
# 3. Audit Log Stream (audit.view)
# ---------------------------------------------------------------------------
@router.get("/audit-logs", response_model=List[AuditLogItem])
def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit.view")),
):
    """Retrieve security and operational audit trail entries."""
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    logs = query.order_by(desc(AuditLog.created_at)).limit(limit).all()

    return [
        AuditLogItem(
            id=log.id,
            user_email=log.user_email,
            action=log.action,
            resource=log.resource,
            details=log.details or {},
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log in logs
    ]


# ---------------------------------------------------------------------------
# 4. System Settings (system.manage)
# ---------------------------------------------------------------------------
@router.get("/settings", response_model=List[SettingItem])
def list_system_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system.manage")),
):
    """Inspect pipeline hyperparameters, ML thresholds, and operational flags."""
    settings = db.query(SystemSetting).order_by(SystemSetting.key.asc()).all()
    if not settings:
        # Seed default operational settings if table is empty
        defaults = [
            ("pipeline.isolation_forest.contamination", {"value": 0.05, "type": "float"}, "Contamination fraction parameter for unsupervised anomaly scoring"),
            ("pipeline.kdtree.neighbor_k", {"value": 5, "type": "int"}, "Number of nearest spatial neighbor AWS stations queried for consistency validation"),
            ("pipeline.retrain.auto_retrain_days", {"value": 7, "type": "int"}, "Automated background model retraining cycle interval"),
            ("notifications.critical_alert_sound", {"value": True, "type": "bool"}, "Play high-frequency auditory alert in operations room for critical faults"),
            ("ingestion.rate_limit_per_min", {"value": 600, "type": "int"}, "Max HTTP ingestion telemetry requests accepted per AWS station node"),
        ]
        for k, v, d in defaults:
            s = SystemSetting(
                key=k,
                value=v,
                description=d,
                updated_by="system",
                updated_at=datetime.now(timezone.utc),
            )
            db.add(s)
        db.commit()
        settings = db.query(SystemSetting).order_by(SystemSetting.key.asc()).all()

    return [
        SettingItem(
            key=s.key,
            value=s.value,
            description=s.description,
            updated_by=s.updated_by,
            updated_at=s.updated_at,
        )
        for s in settings
    ]


@router.post("/settings", response_model=SettingItem)
def update_system_setting(
    payload: SettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("system.manage")),
):
    """Update an operational configuration flag or ML parameter."""
    setting = db.query(SystemSetting).filter(SystemSetting.key == payload.key).first()
    if not setting:
        setting = SystemSetting(
            key=payload.key,
            value=payload.value,
            description=payload.description or "Config setting",
            updated_by=current_user.email,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(setting)
    else:
        setting.value = payload.value
        if payload.description:
            setting.description = payload.description
        setting.updated_by = current_user.email
        setting.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(setting)

    log_audit(
        db=db,
        action="setting_updated",
        resource=f"settings:{payload.key}",
        user=current_user,
        details={"key": payload.key, "new_value": payload.value},
    )

    return SettingItem(
        key=setting.key,
        value=setting.value,
        description=setting.description,
        updated_by=setting.updated_by,
        updated_at=setting.updated_at,
    )
