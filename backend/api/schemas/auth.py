"""
auth.py — Pydantic Schemas for Feature F15 Auth & Role-Gated Access
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid
from storage.models import UserRole


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2)
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.data_quality_officer
