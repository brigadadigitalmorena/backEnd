#!/usr/bin/env python3
"""Check and list existing users in the database"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models import User
from sqlalchemy import select

def main():
    db = SessionLocal()
    try:
        result = db.execute(select(User)).scalars().all()
        print(f'\n=== Total usuarios: {len(result)} ===\n')
        
        if not result:
            print("❌ No hay usuarios en la base de datos")
            return
        
        for user in result:
            print(f'ID: {user.id}')
            print(f'  Email: {user.email}')
            print(f'  Nombre: {user.full_name}')
            print(f'  Rol: {user.role}')
            print(f'  Activo: {user.is_active}')
            print(f'  Creado: {user.created_at}')
            print()
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
