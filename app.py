from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from flask_socketio import SocketIO
import threading, time, io, csv, serial, random, os
from database import init_db, validate_login, get_logs, save_log, get_user_role

app = Flask(__name__)
app.secret_key = 'sterilizer_master_key_87'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global System State
state = {
    "pressure": 0.0, 
    "last_p": 0.0, 
    "status": "STANDBY", 
    "is_running": False, 
    "alert": "",
    "mode": "HARDWARE"
}

# Session Tracking
active_connections = {}
last_disconnect = {}

ser = None
init_db()

def data_handler():
    global ser
    try:
        # Sesuaikan port COM10 sesuai perangkat Anda
        ser = serial.Serial('COM10', 115200, timeout=1)
        state["mode"] = "HARDWARE"
        print("--- HARDWARE DETECTED ON COM10 ---")
    except Exception as e:
        state["mode"] = "SIMULATION"
        print(f"--- SIMULATION MODE ACTIVE: {e} ---")

    while True:
        if state["mode"] == "HARDWARE" and ser and ser.is_open:
            try:
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8').strip()
                    if ',' in line:
                        p_str, s_str = line.split(',')
                        state["pressure"] = float(p_str)
                        state["status"] = s_str
            except Exception as e:
                print(f"Serial Read Error: {e}")
        else:
            # Logic Simulasi
            if state["is_running"]:
                if "STEP" in state["status"] or state["status"] == "FILLING":
                    state["pressure"] += 0.05
                elif "RELEASE" in state["status"]:
                    state["pressure"] -= 0.1
            state["pressure"] = max(0, state["pressure"])

        # Alert dan Auto-Log
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
        if validate_login(request.form['u'], request.form['p']):
            session['user'] = request.form['u']
            # Reset status disconnect agar user tidak langsung ter-kick out karena sesi lama
            if session['user'] in last_disconnect:
                del last_disconnect[session['user']]
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/api/check_login', methods=['POST'])
def check_login():
    data = request.get_json()
    if validate_login(data.get('u'), data.get('p')):
        return jsonify({"valid": True})
    return jsonify({"valid": False})

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    
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
    """Fungsi untuk mengekspor database log ke file CSV"""
    if 'user' not in session: 
        return redirect(url_for('login'))
    
    try:
        # Ambil data dari database melalui fungsi get_logs()
        logs = get_logs() 
        
        # Buat buffer memori untuk file CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Tulis Header
        writer.writerow(['ID', 'Timestamp', 'Pressure (Bar)', 'Status', 'Alert'])
        
        # Tulis Data
        for row in logs:
            writer.writerow(row)
        
        # Pindahkan pointer ke awal buffer
        output.seek(0)
        
        # Konversi StringIO ke BytesIO karena Flask send_file membutuhkan binary stream
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
        print(f"Download Error: {e}")
        return "Gagal mengunduh log", 500

@socketio.on('control')
def handle_control(cmd):
    global ser
    print(f"[COMMAND] {cmd}")
    
    if cmd == 'start': 
        state["is_running"] = True
    elif cmd == 'stop' or cmd == 'reset': 
        state["is_running"] = False
        if cmd == 'reset':
            state["status"] = "EMERGENCY RELEASE"

    if state["mode"] == "HARDWARE" and ser and ser.is_open:
        try:
            ser.write(f"{cmd}\n".encode('utf-8'))
            ser.flush()
        except Exception as e:
            print(f"Send Error: {e}")

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
    import signal, sys

    def signal_handler(sig, frame):
        print("\n")
        confirm = input("\033[33mConfirm server shutdown process. (y/n): \033[0m")
        if confirm.lower() == 'y':
            sys.exit(0)
        else:
            print("Shutdown cancelled. Continuing server operation.")

    signal.signal(signal.SIGINT, signal_handler)
    threading.Thread(target=data_handler, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)