"""User schemas."""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime

from app.models.user import UserRole


# Authentication schemas
class UserLogin(BaseModel):
    """Login request."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"


class UserLoginResponse(BaseModel):
    """User data in login response."""
    id: int
    email: str
    nombre: str
    apellido: str
    rol: str
    telefono: Optional[str] = None
    created_at: datetime
    activo: bool


class LoginResponse(BaseModel):
    """Complete login response with token and user data."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserLoginResponse


class TokenData(BaseModel):
    """Decoded token data."""
    user_id: int
    role: UserRole


# User CRUD schemas
class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: UserRole


class UserCreate(UserBase):
    """Create user request."""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Update user request."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """User response."""
    id: int
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class PasswordResetResponse(BaseModel):
    """Password reset response."""
    message: str
    temporary_password: str
