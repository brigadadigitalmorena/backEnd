"""User router."""
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, Response, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserUpdate, UserResponse, PasswordResetResponse
from app.models.user import UserRole
from app.api.dependencies import AdminUser, AnyUser

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    user_data: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Create a new user (Admin only).
    """
    service = UserService(db)
    return service.create_user(user_data)


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: AnyUser):
    """
    Get current user profile.
    """
    return current_user


@router.get("", response_model=List[UserResponse])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = Query(None, max_length=255)
):
    """
    List all users with optional filters (Admin only).
    """
    service = UserService(db)
    total = service.count_users(role=role, is_active=is_active, search=search)
    response.headers["X-Total-Count"] = str(total)
    return service.get_users(skip=skip, limit=limit, role=role, is_active=is_active, search=search)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Get user by ID (Admin only).
    """
    service = UserService(db)
    return service.get_user(user_id)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Update user (Admin only).
    """
    if user_id == current_user.id and user_data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes desactivar tu propia cuenta"
        )
    service = UserService(db)
    return service.update_user(user_id, user_data)


@router.patch("/me", response_model=UserResponse)
def update_own_profile(
    user_data: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AnyUser
):
    """
    Update own profile (any authenticated user).
    
    Users cannot change their own role or is_active status.
    """
    # Remove sensitive fields that users shouldn't change themselves
    update_data = user_data.model_dump(exclude_unset=True, exclude={'is_active'})
    
    service = UserService(db)
    return service.update_user(current_user.id, UserUpdate(**update_data))


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Soft delete user (Admin only).
    """
    service = UserService(db)
    service.delete_user(user_id)


@router.post("/{user_id}/reset-password", response_model=PasswordResetResponse)
def reset_user_password(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Reset user password to a generated temporary password (Admin only).
    
    Returns the temporary password that should be securely shared with the user.
    """
    service = UserService(db)
    _, temporary_password = service.reset_user_password(user_id)
    
    return PasswordResetResponse(
        message="Contrasena restablecida exitosamente",
        temporary_password=temporary_password
    )
