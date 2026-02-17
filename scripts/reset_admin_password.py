"""Reset admin password to a known value"""
import bcrypt
import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_wIhe4sqi8RuQ@ep-tiny-flower-aitww2p1-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def reset_admin_password():
    """Reset admin password"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # New password
        new_password = "admin123"
        hashed = hash_password(new_password)
        
        # Update admin password
        cur.execute("""
            UPDATE users 
            SET hashed_password = %s
            WHERE email = 'admin@brigada.com'
            RETURNING id, email, full_name
        """, (hashed,))
        
        result = cur.fetchone()
        conn.commit()
        
        if result:
            print("\n✅ Contraseña actualizada exitosamente!\n")
            print("📝 Credenciales de inicio de sesión:")
            print(f"   Email: {result[1]}")
            print(f"   Password: {new_password}")
            print(f"\n🌐 Inicia sesión en:")
            print(f"   http://localhost:3000/login\n")
        else:
            print("\n❌ No se encontró el usuario admin\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")
        raise

if __name__ == "__main__":
    reset_admin_password()
