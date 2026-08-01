from pydantic import BaseModel, ConfigDict, EmailStr, Field

class RegisterRequest(BaseModel):
    workspace_id: str

    full_name: str = Field(
        min_length=3,
        max_length=150,
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=64,
    )

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:str
    workspace_id: str
    full_name: str
    email: EmailStr
    role: str
    is_active: bool