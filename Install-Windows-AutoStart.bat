@echo off
chcp 65001 >nul
title Install Windows Auto-Start — الباحث الحديثي (localhost:8088 Always Ready)
cd /d "%~dp0"

set "TARGET_DIR=%~dp0"
if exist "D:\علمی معاون پرجیکٹ\حدیث سرچ\Start-Background-Silent.vbs" (
    set "TARGET_DIR=D:\علمی معاون پرجیکٹ\حدیث سرچ\"
)

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_VBS=%STARTUP_DIR%\Al-Bahith-Hadith-AutoStart.vbs"

(
echo Set shell = CreateObject^("WScript.Shell"^)
echo shell.CurrentDirectory = "%TARGET_DIR:~0,-1%"
echo shell.Run """%TARGET_DIR%Start-Background-Silent.vbs""", 0, False
) > "%SHORTCUT_VBS%"

echo [OK] Auto-Start registered in Windows Startup folder:
echo      "%SHORTCUT_VBS%"
echo [OK] Starting background server now on http://localhost:8088 and http://localhost:8080 ...
wscript.exe "%TARGET_DIR%Start-Background-Silent.vbs"
timeout /t 2 /nobreak >nul
start "" "http://localhost:8088"
