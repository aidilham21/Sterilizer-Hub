@echo off
setlocal enabledelayedexpansion
title Sterilizer Hub - Git Push Utility
cd /d "%~dp0"

echo ======================================================================
echo                  STERILIZER HUB - GIT PUSH UTILITY                    
echo         Target: https://github.com/aidilham21/sterilizer_hub          
echo ======================================================================
echo.

:: 1. Verifikasi instalasi Git
git --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Git tidak ditemukan! Silakan install Git untuk Windows terlebih dahulu.
    echo.
    pause
    exit /b 1
)

:: 2. Inisialisasi repo Git jika belum ada
if not exist ".git" (
    echo [SETUP] Menginisialisasi repositori Git lokal...
    git init
    git branch -M main
    git remote add origin https://github.com/aidilham21/sterilizer_hub.git
) else (
    :: Pastikan remote origin terpasang dengan benar
    git remote get-url origin >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        git remote add origin https://github.com/aidilham21/sterilizer_hub.git
    ) else (
        git remote set-url origin https://github.com/aidilham21/sterilizer_hub.git
    )
)

echo.
echo [STATUS] Memeriksa perubahan file terkini...
git status -s
echo.

:: 3. Input pesan commit
set "commit_msg=Update Sterilizer Hub codebase and documentation"
set /p "user_msg=Masukkan pesan commit (tekan Enter untuk default '%commit_msg%'): "
if not "!user_msg!"=="" set "commit_msg=!user_msg!"

echo.
echo [1/3] Menambahkan file yang berubah (git add) ...
git add .

echo [2/3] Menyimpan snapshot commit (git commit) ...
git commit -m "!commit_msg!"
if %ERRORLEVEL% neq 0 (
    echo [INFO] Tidak ada perubahan baru untuk di-commit.
)

echo.
echo [3/3] Mengunggah ke GitHub (git push origin main) ...
git push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo ======================================================================
    echo [SUCCESS] Berhasil di-push ke https://github.com/aidilham21/sterilizer_hub
    echo ======================================================================
) else (
    echo.
    echo ======================================================================
    echo [CATATAN] Push gagal atau membutuhkan autentikasi login GitHub.
    echo Jika repo di GitHub sudah memiliki commit berbeda, silakan jalankan 
    echo 'pull.bat' terlebih dahulu sebelum melakukan push kembali.
    echo ======================================================================
)

echo.
pause
