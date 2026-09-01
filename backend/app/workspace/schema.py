from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.auth.model import UserRole


class WorkspaceBase(BaseModel):
    name: str
    slug: str
    logo_url: str | None = None
    website: str | None = None
    industry: str | None = None


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(
        None,
        min_length=2,
        max_length=150,
    )
    slug: str | None = Field(
        None,
        min_length=2,
        max_length=150,
    )
    logo_url: str | None = Field(
        None,
        max_length=500,
    )
    website: str | None = Field(
        None,
        max_length=255,
    )
    industry: str | None = Field(
        None,
        max_length=100,
    )


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    logo_url: str | None = None
    website: str | None = None
    industry: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MemberResponse(BaseModel):
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


class AddMemberRequest(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=150,
    )
    email: EmailStr
    password: str = Field(min_length=8)
    role: UserRole = UserRole.AGENT


class UpdateMemberRoleRequest(BaseModel):
    role: UserRole | None = None
    full_name: str | None = Field(
        None,
        min_length=2,
        max_length=150,
    )
    is_active: bool | None = None


class WorkspaceUserCreateRequest(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=150,
    )
    email: EmailStr
    password: str = Field(min_length=8)
    role: UserRole = UserRole.AGENT


class WorkspaceUserUpdateRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    full_name: str | None = Field(
        None,
        min_length=2,
        max_length=150,
    )


class WorkspaceUserResponse(BaseModel):
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
