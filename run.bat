@echo off
chcp 65001 >nul
title NovaFlix - Sovereign Next-Gen Media Server
echo ========================================================
echo   🎬  NovaFlix - Sovereign Next-Gen Media Platform
echo   Cinema Web Client: http://localhost:8096
echo   Plex-Style Portal: http://localhost:8096/portal
echo ========================================================
echo.

:: Ensure Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH. Please install Python 3.10+.
    pause
    exit /b 1
)

:: Install requirements if needed
echo [*] Checking dependencies...
pip install -r "%~dp0requirements.txt" --quiet

:: Launch NovaFlix
echo [*] Launching NovaFlix Media Engine...
set PYTHONPATH=%~dp0
python -m novaflix.main

pause
