@echo off
setlocal enabledelayedexpansion
title Sterilizer Hub - Git Pull Utility
cd /d "%~dp0"

echo ======================================================================
echo                  STERILIZER HUB - GIT PULL UTILITY                    
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

:: 2. Inisialisasi repo jika belum ada
if not exist ".git" (
    echo [SETUP] Menginisialisasi repositori Git lokal...
    git init
    git branch -M main
    git remote add origin https://github.com/aidilham21/sterilizer_hub.git
) else (
    git remote get-url origin >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        git remote add origin https://github.com/aidilham21/sterilizer_hub.git
    ) else (
        git remote set-url origin https://github.com/aidilham21/sterilizer_hub.git
    )
)

echo [PULL] Mengunduh pembaruan dari GitHub (git pull origin main)...
echo.
git pull origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo ======================================================================
    echo [SUCCESS] Repositori lokal berhasil disinkronkan dengan GitHub.
    echo ======================================================================
) else (
    echo.
    echo ======================================================================
    echo [ERROR] Gagal melakukan pull. Periksa koneksi internet atau konflik lokal.
    echo ======================================================================
)

echo.
pause
