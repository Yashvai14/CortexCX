from dns import message
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    password: str

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
    full_name: str
    email: EmailStr
    role: str

class RegisterResponse(BaseModel):
    message: str

    workspace: WorkspaceResponse

    user: UserResponse
    
    token: TokenResponse
