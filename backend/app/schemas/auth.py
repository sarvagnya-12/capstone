import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    org_name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    org_name: str
    email: EmailStr
    role: UserRole
