#!/usr/bin/env python3
"""Create initial admin user"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import User
from sqlalchemy import select

def create_admin_user():
    """Create an initial admin user for testing"""
    db = SessionLocal()
    try:
        # Check if admin already exists
        admin_email = "admin@brigada.com"
        existing = db.execute(
            select(User).where(User.email == admin_email)
        ).scalar_one_or_none()
        
        if existing:
            print(f"✅ Usuario admin ya existe:")
            print(f"   Email: {existing.email}")
            print(f"   Rol: {existing.role}")
            print(f"   ID: {existing.id}")
            return existing
        
        # Create new admin
        hashed_password = get_password_hash("admin123")
        admin = User(
            email=admin_email,
            hashed_password=hashed_password,
            full_name="Administrador Principal",
            role="admin",
            is_active=True,
            phone="+52 123 456 7890"
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        print("\n✅ Usuario admin creado exitosamente!")
        print(f"   Email: {admin.email}")
        print(f"   Password: admin123")
        print(f"   Rol: {admin.role}")
        print(f"   ID: {admin.id}")
        print("\n⚠️  IMPORTANTE: Cambia esta contraseña después de iniciar sesión\n")
        
        return admin
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_user()
