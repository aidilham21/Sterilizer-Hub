import mysql.connector
from mysql.connector import Error as MySQLError
from werkzeug.security import generate_password_hash, check_password_hash
from contextlib import contextmanager
from config import Config

DB_CONFIG = {
    'host': Config.DB_HOST,
    'port': Config.DB_PORT,
    'user': Config.DB_USER,
    'password': Config.DB_PASSWORD,
    'database': Config.DB_NAME
}

@contextmanager
def get_db(with_database=True):
    """Context manager untuk koneksi database yang aman dan anti-leak."""
    cfg = DB_CONFIG.copy()
    if not with_database:
        cfg.pop('database', None)
    conn = mysql.connector.connect(**cfg)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Inisialisasi skema database dan migrasi keamanan password."""
    try:
        # 1. Pastikan Database Ada
        with get_db(with_database=False) as conn:
            with conn.cursor() as cur:
                # Menggunakan identifier yang disanitasi
                db_name = DB_CONFIG['database'].replace('`', '')
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")

        # 2. Inisialisasi Tabel
        with get_db() as conn:
            with conn.cursor() as cur:
                # Tabel User dengan kolom password 255 karakter untuk hash aman
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY, 
                        username VARCHAR(50) UNIQUE, 
                        password VARCHAR(255),
                        role VARCHAR(20) DEFAULT 'Operator'
                    )
                """)

                # Tabel Log Proses Sterilisasi
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS process_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY, 
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                        pressure FLOAT, 
                        status VARCHAR(50), 
                        alert VARCHAR(100)
                    )
                """)

                # Migrasi: Perbesar panjang kolom password jika tabel lama masih VARCHAR(50)
                try:
                    cur.execute("ALTER TABLE users MODIFY COLUMN password VARCHAR(255)")
                except MySQLError:
                    pass

                # Migrasi: Tambah kolom role jika belum ada
                try:
                    cur.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'Operator'")
                except MySQLError:
                    pass

                # Inisialisasi User Administrator & Operator dari Config / .env
                admin_user = Config.DEFAULT_ADMIN_USER
                admin_pass = Config.DEFAULT_ADMIN_PASSWORD
                operator_user = Config.DEFAULT_OPERATOR_USER
                operator_pass = Config.DEFAULT_OPERATOR_PASSWORD

                admin_hash = generate_password_hash(admin_pass)
                operator_hash = generate_password_hash(operator_pass)

                # Provisioning User Admin
                cur.execute("SELECT id, password FROM users WHERE username = %s", (admin_user,))
                existing_admin = cur.fetchone()
                if not existing_admin:
                    cur.execute(
                        "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                        (admin_user, admin_hash, 'Administrator')
                    )
                elif not existing_admin[1].startswith(('scrypt:', 'pbkdf2:')):
                    cur.execute("UPDATE users SET password = %s, role = 'Administrator' WHERE username = %s", (admin_hash, admin_user))

                # Provisioning User Operator
                cur.execute("SELECT id, password FROM users WHERE username = %s", (operator_user,))
                existing_operator = cur.fetchone()
                if not existing_operator:
                    cur.execute(
                        "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                        (operator_user, operator_hash, 'Operator')
                    )
                elif not existing_operator[1].startswith(('scrypt:', 'pbkdf2:')):
                    cur.execute("UPDATE users SET password = %s, role = 'Operator' WHERE username = %s", (operator_hash, operator_user))

                conn.commit()
        return True
    except MySQLError as e:
        print(f"[DB INIT ERROR] MySQL Error: {e}")
        return False
    except Exception as e:
        print(f"[DB INIT ERROR] Unexpected Error: {e}")
        return False

def validate_login(username, password):
    """Validasi login menggunakan perbandingan hash password aman dan auto-upgrade."""
    if not username or not password:
        return False
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, password FROM users WHERE username = %s", (username,))
                res = cur.fetchone()
                if not res:
                    return False
                
                user_id, stored_hash = res[0], res[1]

                # Jika password masih berupa plaintext lama, verifikasi lalu upgrade ke hash
                if not stored_hash.startswith(('scrypt:', 'pbkdf2:')):
                    if stored_hash == password:
                        new_hash = generate_password_hash(password)
                        cur.execute("UPDATE users SET password = %s WHERE id = %s", (new_hash, user_id))
                        conn.commit()
                        return True
                    return False

                # Verifikasi cryptographic hash
                return check_password_hash(stored_hash, password)
    except MySQLError as e:
        print(f"[AUTH ERROR] Database error during login validation: {e}")
        return False
    except Exception as e:
        print(f"[AUTH ERROR] Unexpected error during login validation: {e}")
        return False

def get_user_role(username):
    """Mengambil role user berdasarkan username."""
    if not username:
        return 'Operator'
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT role FROM users WHERE username = %s", (username,))
                res = cur.fetchone()
                return res[0] if res else 'Operator'
    except Exception as e:
        print(f"[ROLE ERROR] Could not fetch role: {e}")
        return 'Operator'

def get_logs(limit=100):
    """Mengambil riwayat log proses sterilisasi terbaru."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, timestamp, pressure, status, alert FROM process_logs ORDER BY id DESC LIMIT %s",
                    (limit,)
                )
                return cur.fetchall()
    except Exception as e:
        print(f"[LOG ERROR] Could not fetch process logs: {e}")
        return []

def save_log(pressure, status, alert):
    """Menyimpan entri log proses baru ke database."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO process_logs (pressure, status, alert) VALUES (%s, %s, %s)",
                    (float(pressure), str(status), str(alert) if alert else "")
                )
                conn.commit()
                return True
    except Exception as e:
        print(f"[LOG ERROR] Could not save process log: {e}")
        return False
