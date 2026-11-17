from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from flask_socketio import SocketIO
import threading, time, io, csv, serial, os, sys, signal
from config import Config
from database import init_db, validate_login, get_logs, save_log, get_user_role

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['SESSION_COOKIE_HTTPONLY'] = Config.SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SAMESITE'] = Config.SESSION_COOKIE_SAMESITE
app.config['PERMANENT_SESSION_LIFETIME'] = Config.PERMANENT_SESSION_LIFETIME

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Security Headers Middleware
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# Server-side Login Rate Limiter (Anti Brute-Force)
class LoginRateLimiter:
    def __init__(self):
        self.attempts = {}  # ip -> {'count': int, 'lockout_until': float, 'level': int}
        self.lock = threading.Lock()

    def is_locked(self, ip):
        with self.lock:
            info = self.attempts.get(ip)
            if not info:
                return False, 0
            now = time.time()
            if info['lockout_until'] > now:
                return True, int(info['lockout_until'] - now)
            return False, 0

    def record_failure(self, ip):
        with self.lock:
            now = time.time()
            info = self.attempts.setdefault(ip, {'count': 0, 'lockout_until': 0, 'level': 0})
            info['count'] += 1
            threshold = 3 if info['level'] == 0 else 1
            if info['count'] >= threshold:
                duration = 30 if info['level'] == 0 else (60 if info['level'] == 1 else 120)
                info['lockout_until'] = now + duration
                info['level'] = min(info['level'] + 1, 2)
                info['count'] = 0
                return duration, True
            remaining = threshold - info['count']
            return remaining, False

    def reset(self, ip):
        with self.lock:
            self.attempts.pop(ip, None)

rate_limiter = LoginRateLimiter()

# Global System State
state = {
    "pressure": 0.0, 
    "last_p": 0.0, 
    "status": "STANDBY", 
    "is_running": False, 
    "alert": "",
    "mode": "HARDWARE"
}

ALLOWED_COMMANDS = {'start', 'stop', 'reset'}

# Session Tracking
active_connections = {}
last_disconnect = {}

ser = None
init_db()

def data_handler():
    """Background thread untuk membaca serial hardware atau menjalankan logika simulasi."""
    global ser
    try:
        ser = serial.Serial(Config.SERIAL_PORT, Config.SERIAL_BAUDRATE, timeout=Config.SERIAL_TIMEOUT)
        state["mode"] = "HARDWARE"
        print(f"--- HARDWARE DETECTED ON {Config.SERIAL_PORT} ---")
    except Exception as e:
        state["mode"] = "SIMULATION"
        print(f"--- SIMULATION MODE ACTIVE: {e} ---")

    while True:
        if state["mode"] == "HARDWARE" and ser and ser.is_open:
            try:
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                    if ',' in line:
                        parts = line.split(',', 1)
                        state["pressure"] = float(parts[0])
                        state["status"] = parts[1]
            except Exception as e:
                print(f"[SERIAL READ ERROR] {e}")
        else:
            # Logic Simulasi
            if state["is_running"]:
                if "STEP" in state["status"] or state["status"] == "FILLING":
                    state["pressure"] += 0.05
                elif "RELEASE" in state["status"]:
                    state["pressure"] -= 0.1
            state["pressure"] = max(0.0, state["pressure"])

        # Alert dan Proteksi Overpressure
        if state["pressure"] > 4.0: 
            state["alert"] = "DANGER: OVERPRESSURE!"
        else: 
            state["alert"] = ""

        # Simpan log ke database setiap 5 detik saat proses berjalan
        if state["is_running"] and int(time.time()) % 5 == 0:
            save_log(state["pressure"], state["status"], state["alert"])

        socketio.emit('update', state)
        time.sleep(0.5)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        client_ip = request.remote_addr or '127.0.0.1'
        locked, wait_sec = rate_limiter.is_locked(client_ip)
        if locked:
            return render_template('login.html', error=f"LOCKED OUT. WAIT {wait_sec}s")

        u = request.form.get('u', '').strip()
        p = request.form.get('p', '')

        if validate_login(u, p):
            rate_limiter.reset(client_ip)
            session['user'] = u
            if u in last_disconnect:
                del last_disconnect[u]
            return redirect(url_for('index'))
        else:
            left_or_dur, is_locked = rate_limiter.record_failure(client_ip)
            if is_locked:
                err = f"LOCKED OUT. WAIT {left_or_dur}s"
            else:
                err = f"INVALID CREDENTIALS ({left_or_dur} attempts left)"
            return render_template('login.html', error=err)
    return render_template('login.html')

@app.route('/api/check_login', methods=['POST'])
def check_login():
    """API endpoint otentikasi login dengan proteksi rate-limit sisi server."""
    client_ip = request.remote_addr or '127.0.0.1'
    locked, wait_sec = rate_limiter.is_locked(client_ip)
    if locked:
        return jsonify({
            "valid": False, 
            "locked": True, 
            "remaining": wait_sec, 
            "message": f"LOCKED OUT. WAIT {wait_sec}s"
        }), 429

    data = request.get_json(silent=True) or {}
    u = str(data.get('u', '')).strip()
    p = str(data.get('p', ''))

    if not u or not p:
        return jsonify({"valid": False, "message": "Missing credentials"}), 400

    if validate_login(u, p):
        rate_limiter.reset(client_ip)
        return jsonify({"valid": True})
    else:
        left_or_dur, is_locked = rate_limiter.record_failure(client_ip)
        if is_locked:
            return jsonify({
                "valid": False, 
                "locked": True, 
                "remaining": left_or_dur, 
                "message": f"LOCKED OUT. WAIT {left_or_dur}s"
            }), 429
        return jsonify({
            "valid": False, 
            "locked": False, 
            "attempts_left": left_or_dur, 
            "message": f"INVALID CREDENTIALS ({left_or_dur} attempts left)"
        }), 401

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    # Cek apakah user terputus lebih dari 15 detik
    if user in last_disconnect and user not in active_connections:
        if time.time() - last_disconnect[user] > 15:
            session.pop('user', None)
            return redirect(url_for('login'))
            
    role = get_user_role(user)
    return render_template('index.html', user=user, role=role, mode=state["mode"])

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/download')
def download_logs():
    """Fungsi untuk mengekspor database log ke file CSV (Authenticated)."""
    if 'user' not in session: 
        return redirect(url_for('login'))
    
    try:
        logs = get_logs() 
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Timestamp', 'Pressure (Bar)', 'Status', 'Alert'])
        for row in logs:
            writer.writerow(row)
        
        output.seek(0)
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        output.close()

        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'log_sterilizer_{int(time.time())}.csv'
        )
    except Exception as e:
        print(f"[DOWNLOAD ERROR] {e}")
        return "Gagal mengunduh log", 500

@socketio.on('control')
def handle_control(cmd):
    """Handler perintah kontrol sterilisasi dengan otentikasi sesi & validasi whitelist."""
    global ser
    user = session.get('user')
    if not user:
        print(f"[SECURITY BLOCKED] Unauthenticated socket '{request.sid}' attempted command '{cmd}'")
        return False

    if not isinstance(cmd, str) or cmd not in ALLOWED_COMMANDS:
        print(f"[SECURITY BLOCKED] User '{user}' sent unauthorized/invalid command: '{cmd}'")
        return False

    print(f"[AUTHORIZED COMMAND] User: {user} | Command: {cmd}")
    
    if cmd == 'start': 
        state["is_running"] = True
    elif cmd in ('stop', 'reset'): 
        state["is_running"] = False
        if cmd == 'reset':
            state["status"] = "EMERGENCY RELEASE"

    if state["mode"] == "HARDWARE" and ser and ser.is_open:
        try:
            ser.write(f"{cmd}\n".encode('utf-8'))
            ser.flush()
        except Exception as e:
            print(f"[SERIAL SEND ERROR] {e}")

@socketio.on('connect')
def handle_connect():
    user = session.get('user')
    if user:
        if user not in active_connections:
            active_connections[user] = set()
        active_connections[user].add(request.sid)
        last_disconnect.pop(user, None)

@socketio.on('disconnect')
def handle_disconnect():
    user = session.get('user')
    if user and user in active_connections:
        active_connections[user].discard(request.sid)
        if not active_connections[user]:
            del active_connections[user]
            last_disconnect[user] = time.time()

if __name__ == '__main__':
    def clean_shutdown(sig, frame):
        print("\n[INFO] Graceful shutdown initiated...")
        sys.exit(0)

    signal.signal(signal.SIGINT, clean_shutdown)
    threading.Thread(target=data_handler, daemon=True).start()
    socketio.run(
        app, 
        host=Config.APP_HOST, 
        port=Config.APP_PORT, 
        debug=Config.DEBUG, 
        allow_unsafe_werkzeug=True
    )
