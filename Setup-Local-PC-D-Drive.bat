@echo off
chcp 65001 >nul
title Setup Minimal Local PC Runtime — الباحث الحديثي (D:\علمی معاون پرجیکٹ\حدیث سرچ)
cd /d "%~dp0"

echo ============================================================================
echo   الباحث الحديثي (اردو، عربی) — Minimal Local PC Setup (~16.5 MB Only!)
echo   Local Runtime : D:\علمی معاون پرجیکٹ\حدیث سرچ
echo   Cloud Vault   : Google Drive (حدیث سرچ \ cloud_data)
echo ============================================================================

python tools\setup_local_pc_minimal.py --target "D:\علمی معاون پرجیکٹ\حدیث سرچ"
if errorlevel 1 (
    echo [!] Python 3.10+ is required in PATH to install the minimal local runtime.
    pause
    exit /b 1
)

cd /d "D:\علمی معاون پرجیکٹ\حدیث سرچ"
if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Creating local Python virtual environment on D: drive...
    python -m venv .venv
    echo [2/2] Installing FastAPI runtime dependencies...
    ".venv\Scripts\pip.exe" install -r requirements.txt
)

echo.
echo [OK] Minimal Local PC Runtime is ready at: "D:\علمی معاون پرجیکٹ\حدیث سرچ"
echo      All heavy data (3.25 GB) remains exclusively on Google Drive!
echo      Registering silent Windows Auto-Start for http://localhost:8088 & :8080 ...
call "Install-Windows-AutoStart.bat"

