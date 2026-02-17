"""User service."""
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, generate_temporary_password
from app.repositories.user_repository import UserRepository
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """User business logic."""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
    
    def create_user(self, user_data: UserCreate) -> User:
        """
        Create a new user.
        
        Raises:
            HTTPException: If email already exists
        """
        if self.user_repo.exists_by_email(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        hashed_password = get_password_hash(user_data.password)
        
        return self.user_repo.create(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=user_data.role,
            phone=user_data.phone
        )
    
    def get_user(self, user_id: int) -> User:
        """
        Get user by ID.
        
        Raises:
            HTTPException: If user not found
        """
        user = self.user_repo.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user
    
    def get_users(self, skip: int = 0, limit: int = 100,
                  role: Optional[UserRole] = None,
                  is_active: Optional[bool] = None,
                  search: Optional[str] = None) -> List[User]:
        """Get list of users with optional filters."""
        return self.user_repo.get_all(
            skip=skip,
            limit=limit,
            role=role,
            is_active=is_active,
            search=search
        )

    def count_users(self, role: Optional[UserRole] = None,
                    is_active: Optional[bool] = None,
                    search: Optional[str] = None) -> int:
        """Count users with optional filters."""
        return self.user_repo.count_all(role=role, is_active=is_active, search=search)
    
    def update_user(self, user_id: int, user_data: UserUpdate) -> User:
        """
        Update user information.
        
        Raises:
            HTTPException: If user not found or email already exists
        """
        # Check if email is being changed and already exists
        if user_data.email:
            existing = self.user_repo.get_by_email(user_data.email)
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        user = self.user_repo.update(user_id, **user_data.model_dump(exclude_unset=True))
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user
    
    def delete_user(self, user_id: int) -> None:
        """
        Soft delete user.
        
        Raises:
            HTTPException: If user not found
        """
        success = self.user_repo.delete(user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
    
    def reset_user_password(self, user_id: int) -> Tuple[User, str]:
        """
        Reset user password to a generated temporary password.
        
        Returns:
            Tuple of (updated user, temporary password)
        
        Raises:
            HTTPException: If user not found
        """
        user = self.user_repo.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        temporary_password = generate_temporary_password()
        hashed_password = get_password_hash(temporary_password)
        
        updated_user = self.user_repo.update(user_id, hashed_password=hashed_password)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset password"
            )
        
        return updated_user, temporary_password
