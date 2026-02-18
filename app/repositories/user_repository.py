"""User repository."""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.sql import func

from app.models.user import User, UserRole


class UserRepository:
    """User data access layer."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, email: str, hashed_password: str, full_name: str, 
               role: UserRole, phone: Optional[str] = None) -> User:
        """Create a new user."""
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            phone=phone
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID (excludes soft-deleted users)."""
        return (
            self.db.query(User)
            .filter(User.id == user_id, User.deleted_at == None)  # noqa: E711
            .first()
        )
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email (excludes soft-deleted users)."""
        return (
            self.db.query(User)
            .filter(User.email == email, User.deleted_at == None)  # noqa: E711
            .first()
        )
    
    def get_all(self, skip: int = 0, limit: int = 100,
                role: Optional[UserRole] = None,
                is_active: Optional[bool] = None,
                search: Optional[str] = None) -> List[User]:
        """Get all non-deleted users with optional filtering."""
        query = self.db.query(User).filter(User.deleted_at == None)  # noqa: E711
        
        if role is not None:
            query = query.filter(User.role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    User.email.ilike(pattern),
                    User.full_name.ilike(pattern),
                    User.phone.ilike(pattern)
                )
            )
        
        return query.offset(skip).limit(limit).all()

    def count_all(self, role: Optional[UserRole] = None,
                  is_active: Optional[bool] = None,
                  search: Optional[str] = None) -> int:
        """Count non-deleted users with optional filtering."""
        query = self.db.query(User).filter(User.deleted_at == None)  # noqa: E711

        if role is not None:
            query = query.filter(User.role == role)

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    User.email.ilike(pattern),
                    User.full_name.ilike(pattern),
                    User.phone.ilike(pattern)
                )
            )

        return query.count()
    
    def update(self, user_id: int, **kwargs) -> Optional[User]:
        """Update user fields."""
        user = self.get_by_id(user_id)
        if not user:
            return None
        
        for key, value in kwargs.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def delete(self, user_id: int) -> bool:
        """Soft-delete a user: stamp deleted_at and deactivate the account."""
        user = self.get_by_id(user_id)
        if not user:
            return False
        
        user.deleted_at = func.now()
        user.is_active = False
        self.db.commit()
        return True
    
    def exists_by_email(self, email: str) -> bool:
        """Check if a non-deleted user exists with this email."""
        return (
            self.db.query(User)
            .filter(User.email == email, User.deleted_at == None)  # noqa: E711
            .first() is not None
        )
