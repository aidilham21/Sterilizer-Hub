import os
import secrets

# Membaca file .env lokal jika ada (Standard Library, zero dependency)
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    except Exception as e:
        print(f"[CONFIG WARNING] Could not read .env: {e}")

class Config:
    # Flask Security: Gunakan dari .env, atau hasilkan kriptografis acak bila belum ada
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 jam

    # MySQL Database
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_NAME = os.environ.get('DB_NAME', 'sterilizer_db')

    # Initial User Provisioning (Bisa dikonfigurasi via .env)
    DEFAULT_ADMIN_USER = os.environ.get('DEFAULT_ADMIN_USER', 'admin')
    DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD', 'admin123')
    DEFAULT_OPERATOR_USER = os.environ.get('DEFAULT_OPERATOR_USER', 'idil')
    DEFAULT_OPERATOR_PASSWORD = os.environ.get('DEFAULT_OPERATOR_PASSWORD', 'idil123')

    # Serial Communication (Hardware)
    SERIAL_PORT = os.environ.get('SERIAL_PORT', 'COM10')
    SERIAL_BAUDRATE = int(os.environ.get('SERIAL_BAUDRATE', 115200))
    SERIAL_TIMEOUT = float(os.environ.get('SERIAL_TIMEOUT', 1.0))

    # Server Settings
    APP_HOST = os.environ.get('APP_HOST', '0.0.0.0')
    APP_PORT = int(os.environ.get('APP_PORT', 5000))
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')

    # Security: Brute-Force Rate Limiting
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_SEC = 30
