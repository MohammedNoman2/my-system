from typing import Optional
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    user_id: int
    username: str
    full_name: str
    role: UserRole
    csrf_token: str


TokenResponse = LoginResponse


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: UserRole
    email: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True
