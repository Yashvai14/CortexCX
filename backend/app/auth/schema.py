from datetime import datetime
from uuid import UUID
from app.auth.model import UserRole
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =====================================================
# Request Schemas
# =====================================================

class RegisterRequest(BaseModel):
    company_name: str = Field(
        min_length=2,
        max_length=150,
    )

    company_slug: str = Field(
        min_length=2,
        max_length=150,
        pattern=r"^[a-z0-9-]+$",
    )

    full_name: str = Field(
        min_length=2,
        max_length=150,
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=64,
    )


class LoginRequest(BaseModel):
    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=64,
    )


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserCreateRequest(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=150,
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=64,
    )

    role: UserRole = UserRole.AGENT


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(
        None,
        min_length=2,
        max_length=150,
    )

    email: EmailStr | None = None

    password: str | None = Field(
        None,
        min_length=8,
        max_length=64,
    )

    role: UserRole | None = None

    is_active: bool | None = None


class MessageResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID

    full_name: str
    email: EmailStr

    role: UserRole

    is_active: bool
    is_verified: bool

    created_at: datetime
    updated_at: datetime


class RegisterResponse(BaseModel):
    message: str

    workspace: WorkspaceResponse
    user: UserResponse
    token: TokenResponse


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

    user: UserResponse