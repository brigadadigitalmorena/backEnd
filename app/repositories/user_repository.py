"""User repository."""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

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
        """Get user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.db.query(User).filter(User.email == email).first()
    
    def get_all(self, skip: int = 0, limit: int = 100,
                role: Optional[UserRole] = None,
                is_active: Optional[bool] = None,
                search: Optional[str] = None) -> List[User]:
        """Get all users with optional filtering."""
        query = self.db.query(User)
        
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
        """Count users with optional filtering."""
        query = self.db.query(User)

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
        """Soft delete user (set is_active to False)."""
        user = self.get_by_id(user_id)
        if not user:
            return False
        
        user.is_active = False
        self.db.commit()
        return True
    
    def exists_by_email(self, email: str) -> bool:
        """Check if user exists by email."""
        return self.db.query(User).filter(User.email == email).first() is not None
