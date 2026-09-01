from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.customer.model import CustomerStatus


class CustomerCreateRequest(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=150,
    )
    email: EmailStr
    phone: str | None = Field(
        None,
        max_length=50,
    )
    company_name: str | None = Field(
        None,
        max_length=150,
    )
    status: CustomerStatus = CustomerStatus.ACTIVE


class CustomerUpdateRequest(BaseModel):
    full_name: str | None = Field(
        None,
        min_length=2,
        max_length=150,
    )
    email: EmailStr | None = None
    phone: str | None = Field(
        None,
        max_length=50,
    )
    company_name: str | None = Field(
        None,
        max_length=150,
    )
    status: CustomerStatus | None = None


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    full_name: str
    email: EmailStr
    phone: str | None = None
    company_name: str | None = None
    status: CustomerStatus
    created_at: datetime
    updated_at: datetime
