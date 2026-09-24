"""
permissions.py — Granular Role-Based Access Control (RBAC) & Permissions Matrix
AeroSentinel (SIH26073)

Defines the 21 explicit permissions across 4 functional domains:
1. Overview (dashboard, fleet)
2. Monitoring (stations, telemetry, alerts, anomalies, forecasts, health)
3. Operations (maintenance, data upload)
4. Administration (users, roles, audit, system)
"""

from typing import Dict, List, Tuple, Optional, Callable
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from storage.db import get_db
from storage.models import User, UserRole, AuditLog


# ---------------------------------------------------------------------------
# 1. Complete Permission Catalog (21 explicit permissions)
# ---------------------------------------------------------------------------
ALL_PERMISSIONS: Dict[str, Tuple[str, str]] = {
    # Overview
    "dashboard.view": ("overview", "View role-customized operational dashboard"),
    "fleet.view": ("overview", "View interactive geographic AWS fleet map"),

    # Monitoring
    "stations.view": ("monitoring", "Inspect station sensor telemetry and status"),
    "stations.edit": ("monitoring", "Modify station metadata and operational limits"),
    "telemetry.view": ("monitoring", "Stream real-time high-frequency sensor readings"),
    "alerts.view": ("monitoring", "Browse system anomaly alert feed"),
    "alerts.acknowledge": ("monitoring", "Acknowledge and claim sensor anomaly alerts"),
    "anomalies.view": ("monitoring", "Inspect machine learning anomaly detections"),
    "anomalies.investigate": ("monitoring", "Triage anomaly evidence, SHAP attribution, and KDTree bounds"),
    "anomalies.resolve": ("monitoring", "Resolve anomaly state and submit QC decision"),
    "forecasts.view": ("monitoring", "View meteorological forecasts and extreme weather trends"),
    "forecasts.create": ("monitoring", "Issue localized severe weather warning bulletin"),
    "health.view": ("monitoring", "Inspect system health, database, and pipeline status"),

    # Operations
    "maintenance.view": ("operations", "View predictive maintenance failure risks"),
    "maintenance.update": ("operations", "Schedule technician dispatch and work orders"),
    "data.upload": ("operations", "Ingest external sensor data files (CSV/JSON)"),

    # Administration
    "users.view": ("administration", "View registered personnel and accounts"),
    "users.manage": ("administration", "Create, edit, and deactivate user accounts"),
    "roles.manage": ("administration", "Configure roles and assign granular permissions"),
    "audit.view": ("administration", "Inspect security and data access audit trail"),
    "system.manage": ("administration", "Configure pipeline hyperparameters and models"),
}


# ---------------------------------------------------------------------------
# 2. Role Permissions Matrix
# ---------------------------------------------------------------------------
ROLE_PERMISSIONS_MAP: Dict[str, List[str]] = {
    # ADMIN: Full access across all 21 permissions
    "admin": list(ALL_PERMISSIONS.keys()),

    # FORECASTER: Weather operations, forecasts, anomalies, fleet, alerts
    "forecaster": [
        "dashboard.view",
        "fleet.view",
        "telemetry.view",
        "stations.view",
        "alerts.view",
        "alerts.acknowledge",
        "anomalies.view",
        "anomalies.investigate",
        "forecasts.view",
        "forecasts.create",
        "health.view",
    ],

    # QC ANALYST: Anomaly triage, evidence review, data upload, feedback
    "qc_analyst": [
        "dashboard.view",
        "fleet.view",
        "telemetry.view",
        "stations.view",
        "alerts.view",
        "alerts.acknowledge",
        "anomalies.view",
        "anomalies.investigate",
        "anomalies.resolve",
        "health.view",
        "data.upload",
    ],

    # Data Quality Officer (backward compatibility alias for qc_analyst)
    "data_quality_officer": [
        "dashboard.view",
        "fleet.view",
        "telemetry.view",
        "stations.view",
        "alerts.view",
        "alerts.acknowledge",
        "anomalies.view",
        "anomalies.investigate",
        "anomalies.resolve",
        "health.view",
        "data.upload",
    ],

    # FIELD TECHNICIAN: Station hardware, maintenance queue, fleet map, health
    "field_technician": [
        "fleet.view",
        "stations.view",
        "stations.edit",
        "health.view",
        "maintenance.view",
        "maintenance.update",
    ],

    # VIEWER: Read-only monitoring
    "viewer": [
        "dashboard.view",
        "fleet.view",
        "stations.view",
        "telemetry.view",
        "alerts.view",
    ],
}


def get_user_permissions(user: User) -> List[str]:
    """Retrieve explicit permission codes for a given user based on active role."""
    role_key = user.role.value if hasattr(user.role, "value") else str(user.role)
    return ROLE_PERMISSIONS_MAP.get(role_key, ROLE_PERMISSIONS_MAP.get("viewer", []))


# ---------------------------------------------------------------------------
# 3. Audit Trail Logging Helper
# ---------------------------------------------------------------------------
def log_audit(
    db: Session,
    action: str,
    resource: str,
    user: Optional[User] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Record an audit log entry for security and compliance."""
    try:
        user_email = user.email if user else "anonymous/system"
        user_id = user.id if user else None
        audit_entry = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource=resource,
            details=details or {},
            ip_address=ip_address or "127.0.0.1",
        )
        db.add(audit_entry)
        db.commit()
    except Exception:
        # Prevent audit logging failure from failing the main transaction
        db.rollback()


# ---------------------------------------------------------------------------
# 4. FastAPI Dependency Factory: require_permission
# ---------------------------------------------------------------------------
def require_permission(permission_code: str) -> Callable:
    """
    FastAPI dependency ensuring the authenticated user has the explicit permission.
    Raises 403 Forbidden if unauthorized.
    """
    from core.auth import get_current_user

    def permission_checker(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        user_permissions = get_user_permissions(current_user)
        if permission_code not in user_permissions:
            role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
            # Log unauthorized attempt
            client_ip = request.client.host if request.client else "unknown"
            log_audit(
                db=db,
                action="access_denied",
                resource=permission_code,
                user=current_user,
                details={"required_permission": permission_code, "user_role": role_str},
                ip_address=client_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: You lack the required permission '{permission_code}'. Role '{role_str}' cannot perform this action.",
            )
        return current_user

    return permission_checker
