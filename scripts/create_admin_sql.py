"""Create admin user via SQL"""
import bcrypt
import psycopg2
from datetime import datetime

# Database connection
DATABASE_URL = "postgresql://neondb_owner:npg_wIhe4sqi8RuQ@ep-tiny-flower-aitww2p1-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def create_admin():
    """Create admin user"""
    try:
        # Connect to database
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Check if admin exists
        cur.execute("SELECT id, email, role FROM users WHERE email = %s", ("admin@brigada.com",))
        existing = cur.fetchone()
        
        if existing:
            print(f"\n✅ Usuario admin ya existe:")
            print(f"   ID: {existing[0]}")
            print(f"   Email: {existing[1]}")
            print(f"   Rol: {existing[2]}")
            print()
            cur.close()
            conn.close()
            return
        
        # Hash password
        password = "admin123"
        hashed_password = hash_password(password)
        
        # Insert admin user
        now = datetime.utcnow()
        cur.execute("""
            INSERT INTO users (email, hashed_password, full_name, role, is_active, phone, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, email, role
        """, (
            "admin@brigada.com",
            hashed_password,
            "Administrador Principal",
            "admin",
            True,
            "+52 123 456 7890",
            now,
            now
        ))
        
        result = cur.fetchone()
        conn.commit()
        
        print("\n✅ Usuario admin creado exitosamente!")
        print(f"   ID: {result[0]}")
        print(f"   Email: {result[1]}")
        print(f"   Password: {password}")
        print(f"   Rol: {result[2]}")
        print("\n⚠️  IMPORTANTE: Cambia esta contraseña después de iniciar sesión")
        print("\n📝 Puedes iniciar sesión en el CMS con estas credenciales:\n")
        print(f"   http://localhost:3000/login")
        print(f"   Email: {result[1]}")
        print(f"   Password: {password}\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")
        raise

if __name__ == "__main__":
    create_admin()
