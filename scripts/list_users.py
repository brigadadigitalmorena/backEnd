"""List all users in the database"""
import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_wIhe4sqi8RuQ@ep-tiny-flower-aitww2p1-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"

def list_users():
    """List all users"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, email, full_name, role, is_active, created_at 
            FROM users 
            ORDER BY created_at DESC
        """)
        
        users = cur.fetchall()
        
        print(f"\n=== Total usuarios: {len(users)} ===\n")
        
        if not users:
            print("❌ No hay usuarios en la base de datos\n")
            return
        
        admins = []
        encargados = []
        brigadistas = []
        
        for user in users:
            user_id, email, full_name, role, is_active, created_at = user
            status = "✅" if is_active else "❌"
            
            if role.upper() == "ADMIN":
                admins.append((user_id, email, full_name, status))
            elif role.upper() == "ENCARGADO":
                encargados.append((user_id, email, full_name, status))
            else:
                brigadistas.append((user_id, email, full_name, status))
        
        # Print admins
        if admins:
            print("👑 ADMINISTRADORES:")
            for user_id, email, full_name, status in admins:
                print(f"   {status} ID: {user_id} | {email} | {full_name}")
            print()
        
        # Print encargados
        if encargados:
            print("👥 ENCARGADOS:")
            for user_id, email, full_name, status in encargados:
                print(f"   {status} ID: {user_id} | {email} | {full_name}")
            print()
        
        # Print brigadistas
        if brigadistas:
            print("🎯 BRIGADISTAS:")
            for user_id, email, full_name, status in brigadistas:
                print(f"   {status} ID: {user_id} | {email} | {full_name}")
            print()
        
        # Summary for whitelist creation
        supervisors = admins + encargados
        if supervisors:
            print(f"✅ Supervisores disponibles: {len(supervisors)}")
            print("   Puedes crear brigadistas asignándolos a estos supervisores.\n")
        else:
            print("⚠️  No hay supervisores (Admins o Encargados).")
            print("   Necesitas crear al menos un Encargado para asignar Brigadistas.\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")
        raise

if __name__ == "__main__":
    list_users()
