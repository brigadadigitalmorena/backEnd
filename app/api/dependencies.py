"""API dependencies for authentication and authorization."""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

# Security scheme
security = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[Session, Depends(get_db)]
) -> User:
    """
    Dependency to get current authenticated user.
    
    Extracts JWT from Bearer token, validates it, and retrieves user.
    
    Raises:
        HTTPException: If token invalid or user not found
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(int(user_id))
    
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return user


def require_role(*allowed_roles: UserRole):
    """
    Dependency factory for role-based access control.
    
    Usage:
        @app.get("/admin-only")
        def admin_endpoint(user: User = Depends(require_role(UserRole.ADMIN))):
            ...
    
    Args:
        *allowed_roles: Roles that are allowed to access the endpoint
    
    Returns:
        Dependency function that checks user role
    """
    def role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        return current_user
    
    return role_checker


# Common role dependencies
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
EncargadoUser = Annotated[User, Depends(require_role(UserRole.ENCARGADO))]
BrigadistaUser = Annotated[User, Depends(require_role(UserRole.BRIGADISTA))]
AdminOrEncargado = Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.ENCARGADO))]
MobileUser = Annotated[User, Depends(require_role(UserRole.BRIGADISTA, UserRole.ENCARGADO))]
AnyUser = Annotated[User, Depends(get_current_user)]
