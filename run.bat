@echo off
setlocal enabledelayedexpansion
title Sterilizer Hub - App Launcher
cd /d "%~dp0"

echo ======================================================================
echo                  STERILIZER HUB - LAUNCHER                           
echo ======================================================================
echo.

:: 1. Cek Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python tidak ditemukan! Pastikan Python sudah terinstall dan ada di PATH.
    pause
    exit /b 1
)

:: 2. Cek apakah MySQL sudah berjalan (port 3306)
powershell -Command "$c = Test-NetConnection -ComputerName 127.0.0.1 -Port 3306 -WarningAction SilentlyContinue; exit ($c.TcpTestSucceeded ? 0 : 1)" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] MySQL belum aktif, mencoba menjalankan MySQL dari XAMPP...
    if exist "C:\xampp\mysql\bin\mysqld.exe" (
        start /b "" "C:\xampp\mysql\bin\mysqld.exe" --defaults-file="C:\xampp\mysql\bin\my.ini" --standalone
        timeout /t 3 /nobreak >nul
    ) else (
        echo [WARNING] XAMPP MySQL tidak ditemukan di C:\xampp. Pastikan MySQL sudah berjalan secara manual!
    )
) else (
    echo [OK] MySQL aktif di port 3306.
)

:: 3. Buka browser otomatis ke localhost:5000 setelah jeda singkat
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: 4. Jalankan aplikasi Flask Sterilizer Hub
echo [INFO] Memulai Sterilizer Hub di http://localhost:5000 ...
echo [INFO] Tekan Ctrl+C di terminal ini untuk mematikan server.
echo.
python app.py

pause
