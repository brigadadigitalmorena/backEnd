"""Authentication router."""
from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, Body, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.services.auth_service import AuthService
from app.schemas.user import LoginResponse, UserResponse
from app.core.security import decode_refresh_token, create_access_token, create_refresh_token
from app.repositories.user_repository import UserRepository
from app.api.dependencies import AnyUser
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)]
):
    """
    Login with email and password.
    
    Accepts FormData with:
    - username: user email
    - password: user password
    
    Returns JWT access token with user data.
    """
    auth_service = AuthService(db)
    # OAuth2PasswordRequestForm uses "username" field for email
    return auth_service.login(form_data.username, form_data.password)


@router.post("/logout")
def logout(
    db: Annotated[Session, Depends(get_db)],
    current_user: AnyUser
):
    """
    Logout current user.
    Increments token_version to invalidate all current refresh tokens.
    """
    current_user.token_version = (current_user.token_version or 1) + 1
    db.add(current_user)
    db.commit()
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: AnyUser):
    """
    Get current authenticated user's information.
    
    Requires valid JWT token in Authorization header.
    """
    return current_user


@router.post("/refresh")
def refresh_token(
    db: Annotated[Session, Depends(get_db)],
    refresh_token: str = Body(..., embed=True)
):
    """
    Refresh access token using refresh token (with token rotation).
    
    The old refresh token is invalidated after use — a new one is returned.
    """
    payload = decode_refresh_token(refresh_token)
    user_id = payload.get("sub")
    token_ver = payload.get("ver")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    repo = UserRepository(db)
    user = repo.get_by_id(int(user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Token rotation: verify version matches, then increment
    if token_ver is not None and token_ver != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    # Increment version to invalidate this refresh token
    user.token_version = (user.token_version or 1) + 1
    db.add(user)
    db.commit()

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.id), "role": user.role.value, "ver": user.token_version},
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    return {"access_token": access_token, "refresh_token": new_refresh_token}
