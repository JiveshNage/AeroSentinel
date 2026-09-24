"""
auth.py — Authentication REST Endpoints (F15)
Feature: F15 — Auth & roles (Phase 5 Stretch Goal)

Endpoints:
- POST /api/auth/login: authenticates credentials and returns JWT Bearer token
- GET /api/auth/me: inspects current authenticated user identity and role
- POST /api/auth/register: registers new system user
"""

from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from storage.db import get_db
from storage.models import User, UserRole
from core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_roles,
)
from api.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    RegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate user with email and password.
    Returns HS256 JWT access token and user role profile.
    """
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user)
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            name=user.name,
            email=user.email,
            role=role_str,
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserResponse)
def get_authenticated_user_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve authenticated user identity and active role.
    Requires valid Bearer token.
    """
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        role=role_str,
        created_at=current_user.created_at,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new user account with role assignment.
    """
    existing = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    user = User(
        id=uuid.uuid4(),
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        role=payload.role,
        password_hash=hash_password(payload.password),
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    return UserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=role_str,
        created_at=user.created_at,
    )


# ---------------------------------------------------------------------------
# Role-Gated Protected Demonstration Endpoints (F15 Exit Criteria)
# ---------------------------------------------------------------------------

@router.get("/admin-only")
def admin_only_resource(
    current_user: User = Depends(require_roles(UserRole.admin)),
):
    """Restricted to System Administrators (governance, retrain, fleet config)."""
    return {
        "message": "Welcome, Administrator. Access granted to privileged governance console.",
        "user": current_user.email,
        "role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
    }


@router.get("/dqo-only")
def dqo_only_resource(
    current_user: User = Depends(require_roles(UserRole.data_quality_officer, UserRole.admin)),
):
    """Restricted to Data Quality Officers and Administrators (QC triage, feedback)."""
    return {
        "message": "Access granted to Data Quality Officer triage console.",
        "user": current_user.email,
        "role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
    }


@router.get("/tech-only")
def technician_only_resource(
    current_user: User = Depends(require_roles(UserRole.field_technician, UserRole.admin)),
):
    """Restricted to Field Maintenance Technicians and Administrators (maintenance queue)."""
    return {
        "message": "Access granted to Field Technician maintenance dispatch queue.",
        "user": current_user.email,
        "role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
    }

