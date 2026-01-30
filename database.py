import mysql.connector

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'sterilizer_db'
}

def init_db():
    try:
        conn = mysql.connector.connect(host=DB_CONFIG['host'], user=DB_CONFIG['user'], password=DB_CONFIG['password'])
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        conn.close()
        
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        # Fitur 4 & 5: Tabel User
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY, 
                username VARCHAR(50) UNIQUE, 
                password VARCHAR(50),
                role VARCHAR(20) DEFAULT 'Operator'
            )
        """)
        # Fitur 10 & 11: Tabel Log
        cur.execute("""
            CREATE TABLE IF NOT EXISTS process_logs (
                id INT AUTO_INCREMENT PRIMARY KEY, 
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                pressure FLOAT, 
                status VARCHAR(50), 
                alert VARCHAR(100)
            )
        """)
        
        # Update struktur tabel jika sudah ada (Migration)
        try:
            cur.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'Operator'")
        except: pass

        cur.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'Administrator') ON DUPLICATE KEY UPDATE role='Administrator'")
        cur.execute("INSERT INTO users (username, password, role) VALUES ('idil', 'idil123', 'Operator') ON DUPLICATE KEY UPDATE role='Operator'")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database Error: {e}")
        return False

def validate_login(u, p):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (u, p))
        res = cur.fetchone()
        conn.close()
        return res is not None
    except: return False

def get_user_role(u):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username=%s", (u,))
        res = cur.fetchone()
        conn.close()
        return res[0] if res else 'Operator'
    except: return 'Operator'

def get_logs():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT * FROM process_logs ORDER BY id DESC LIMIT 100")
        res = cur.fetchall()
        conn.close()
        return res
    except: return []

def save_log(p, s, a):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("INSERT INTO process_logs (pressure, status, alert) VALUES (%s, %s, %s)", (p, s, a))
        conn.commit()
        conn.close()
    except: pass