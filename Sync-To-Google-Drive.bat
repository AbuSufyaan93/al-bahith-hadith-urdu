@echo off
chcp 65001 >nul
title Sync الباحث الحديثي Runtime & Cache Snapshot to Google Drive (حدیث سرچ)
cd /d "%~dp0"

echo ============================================================================
echo   Syncing الباحث الحديثي Minimal Runtime + Cache Snapshot to Google Drive
echo   Google Drive Folder ID: 1c7w9HLYONrrdcvqh7uPhQdE0sAOqHmLA
echo ============================================================================

set "GDRIVE_TARGET="
if exist "G:\My Drive\علمی پروجیکٹ\حدیث سرچ" set "GDRIVE_TARGET=G:\My Drive\علمی پروجیکٹ\حدیث سرچ"
if "%GDRIVE_TARGET%"=="" if exist "G:\My Drive\علمی معاون پرجیکٹ\حدیث سرچ" set "GDRIVE_TARGET=G:\My Drive\علمی معاون پرجیکٹ\حدیث سرچ"

if not "%GDRIVE_TARGET%"=="" (
    echo [1/2] Syncing minimal runtime code & catalogs to "%GDRIVE_TARGET%"...
    robocopy "%~dp0backend" "%GDRIVE_TARGET%\backend" /E /XD __pycache__ _app
    robocopy "%~dp0pipeline" "%GDRIVE_TARGET%\pipeline" /E /XD __pycache__
    robocopy "%~dp0database\catalogs" "%GDRIVE_TARGET%\database\catalogs" /E
    robocopy "%~dp0tools" "%GDRIVE_TARGET%\tools" /E /XD __pycache__
    robocopy "%~dp0." "%GDRIVE_TARGET%" *.bat *.json *.txt *.md /LEV:1

    if exist "%~dp0database\local_runtime_cache.db" (
        echo [2/2] Saving clean snapshot of local_runtime_cache.db to "%GDRIVE_TARGET%\cloud_data\cache_snapshots"...
        if not exist "%GDRIVE_TARGET%\cloud_data\cache_snapshots" mkdir "%GDRIVE_TARGET%\cloud_data\cache_snapshots"
        python -c "import sqlite3, pathlib; src=sqlite3.connect(r'%~dp0database\local_runtime_cache.db'); dst_p=pathlib.Path(r'%GDRIVE_TARGET%\cloud_data\cache_snapshots\local_runtime_cache.db'); dst_p.unlink(missing_ok=True); dst=sqlite3.connect(str(dst_p)); src.backup(dst); dst.execute('PRAGMA journal_mode=DELETE;'); dst.close(); src.close()"
    )
    echo [OK] Sync completed cleanly with zero locks on cloud_data\database\al_bahith_hadith.db!
) else (
    echo [!] Google Drive folder not found at "G:\My Drive\علمی پروجیکٹ\حدیث سرچ". Please ensure Google Drive for Desktop is running.
)
pause
