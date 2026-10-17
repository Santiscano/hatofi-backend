from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.userModel import RoleEnum


class RoleResponse(BaseModel):
    id: int
    name: RoleEnum
    description: str | None = None
    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    role_id: int
    terms_accepted: bool


class UserUpdatePassword(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


class UserResponse(UserBase):
    id: int
    is_active: bool
    terms_accepted: bool
    created_at: datetime
    role: RoleResponse
    model_config = ConfigDict(from_attributes=True)


class UserAuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
