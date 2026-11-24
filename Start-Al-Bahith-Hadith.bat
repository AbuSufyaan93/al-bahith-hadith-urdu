@echo off
chcp 65001 >nul
title الباحث الحديثي — اردو، عربی (Cloud Vault + Minimal Local PC Server)
cd /d "%~dp0"

echo ============================================================================
echo   الباحث الحديثي — اردو، عربی (Al-Bahith Al-Hadithi — Salafi Urdu Edition)
echo   Architecture: Google Drive Master Vault + Minimal Local PC (~16.5 MB)
echo ============================================================================

rem 1. If launched from Google Drive (e.g. G:\My Drive\...), automatically sync & switch to D:\علمی معاون پرجیکٹ\حدیث سرچ
echo "%~dp0" | findstr /I "Drive" >nul
if %errorlevel%==0 (
    if exist "D:\" (
        echo [Cloud->Local] Syncing minimal ~16.5 MB runtime to "D:\علمی معاون پرجیکٹ\حدیث سرچ"...
        python "%~dp0tools\setup_local_pc_minimal.py" --target "D:\علمی معاون پرجیکٹ\حدیث سرچ" --cloud-dir "%~dp0."
        cd /d "D:\علمی معاون پرجیکٹ\حدیث سرچ"
    )
)

rem 2. Auto-start Google Drive for Desktop if installed and G:\My Drive is not yet mounted
if not exist "G:\My Drive" (
    if exist "%ProgramFiles%\Google\Drive File Stream" (
        for /f "delims=" %%g in ('dir /b /s "%ProgramFiles%\Google\Drive File Stream\GoogleDriveFS.exe" 2^>nul') do (
            echo [Cloud Vault] Starting Google Drive for Desktop...
            start "" "%%g"
            timeout /t 5 /nobreak >nul
            goto :drive_checked
        )
    )
)
:drive_checked

rem 3. Create local .venv on D: drive if not present
if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Creating local Python virtual environment...
    python -m venv .venv
    echo [2/2] Installing FastAPI runtime packages...
    ".venv\Scripts\pip.exe" install -r requirements.txt
)

rem 4. Keep local PC folder strictly minimal (purges any heavy bloat already safe on Google Drive)
".venv\Scripts\python.exe" tools\setup_local_pc_minimal.py --clean-self

echo [Ready] Starting الباحث الحديثي on BOTH http://localhost:8088 and http://localhost:8080 (IPv4 + IPv6)...
".venv\Scripts\python.exe" tools\run_local_server.py --ports 8088,8080 --open-browser
if errorlevel 1 (
    pause
)

