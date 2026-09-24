"""
auth.py — Authentication & Role-Based Access Control (RBAC) (F15)
Feature: F15 — Auth & roles (Phase 5 Stretch Goal)

1. Salted PBKDF2-HMAC-SHA256 password hashing and constant-time verification.
2. HS256 JWT access token generation and cryptographic decoding.
3. get_current_user and require_roles FastAPI dependency factories enforcing 403 Forbidden.
"""

from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import secrets
from typing import Optional, List, Dict, Any, Callable
import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.config import settings
from storage.db import get_db
from storage.models import User, UserRole

# HTTP Bearer scheme
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# 1. Password Hashing & Verification
# ---------------------------------------------------------------------------

def hash_password(plain_password: str) -> str:
    """
    Hash a plaintext password using PBKDF2-HMAC-SHA256 with a cryptographically
    secure 16-byte random salt and 100,000 iterations.
    """
    salt = secrets.token_bytes(16)
    iterations = 100_000
    derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored PBKDF2 hash using constant-time comparison.
    """
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_hash = parts[3]

        computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(computed.hex(), expected_hash)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 2. JWT Generation & Verification
# ---------------------------------------------------------------------------

def create_access_token(user: User, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generate an HS256 JWT access token encoding user ID, email, role, and expiration.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    from core.permissions import get_user_permissions

    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    permissions = get_user_permissions(user)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": role_val,
        "permissions": permissions,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate JWT access token signature and expiration.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# 3. FastAPI Dependencies & Role Gating
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Authenticate user via Bearer token in Authorization header.
    Raises 401 if unauthenticated, token expired, or user not found.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identity.",
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity format.",
        )

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
        )

    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Optional user extractor: returns User if valid Bearer token provided, None otherwise.
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        return db.query(User).filter(User.id == uuid.UUID(user_id_str)).first()
    except Exception:
        return None


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """
    Factory creating a FastAPI dependency enforcing Role-Based Access Control (RBAC).
    Raises 403 Forbidden if authenticated user's role is not within permitted roles.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = (
            current_user.role
            if isinstance(current_user.role, UserRole)
            else UserRole(str(current_user.role))
        )
        if user_role not in roles:
            allowed = [r.value for r in roles]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Operation requires one of the following roles: {allowed}. Your role is '{user_role.value}'.",
            )
        return current_user

    return role_checker
