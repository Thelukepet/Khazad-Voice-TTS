@echo off
title KHAZAD VOICE - ECHOES OF ANGMAR
color 0E

:: 1. Check Environment
if not exist venv (
    echo [ERROR] 'venv' not found. Please run install.bat.
    pause
    exit
)

:: 2. Activate Venv
call venv\Scripts\activate.bat

:: 3. AUTO-UPDATE SEQUENCE
echo [UPDATE] Checking for updates...
git fetch origin main >nul 2>&1

:: Check if we are behind origin/main
git status -uno | find "behind" >nul
if %errorlevel%==0 (
    echo [UPDATE] New version found! Downloading...
    git pull origin main

    if errorlevel 1 (
        echo [WARNING] Could not update automatically (Local changes detected).
        timeout /t 3
    ) else (
        echo [UPDATE] Syncing dependencies...
        :: INSTANT CHECK WITH UV
        uv pip install -q -r requirements.txt
    )
)

:: 4. Launch
echo.
echo [INFO] Starting Echoes of Angmar Mode...
python main.py --mode echoes
pause