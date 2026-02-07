@echo off
title KHAZAD VOICE TTS - LAUNCHER
color 0E

echo ==================================================
echo               KHAZAD VOICE TTS
echo      "Baruk Khazad! The Voice of LOTRO!"
echo ==================================================
echo.

:: --- 1. Check for Environment ---
if not exist venv (
    echo [ERROR] Virtual environment 'venv' folder not found.
    echo Please run 'install.bat' first to set up the application.
    echo.
    pause
    exit
)

:: --- 2. Check for Main Script ---
if not exist main.py (
    echo [ERROR] 'main.py' not found in this folder.
    echo Make sure you are running start.bat from the project root.
    echo.
    pause
    exit
)

:: --- 3. Launch ---
echo [INFO] Activating AI Core...
:: Using .bat extension explicitly is safer
call venv\Scripts\activate.bat

echo [INFO] Starting Application...
echo.
python main.py

:: --- 4. Final Status Check ---
if %errorlevel% neq 0 (
    echo.
    echo ==================================================
    echo [CRITICAL] The application crashed!
    echo Read the error message above (traceback).
    echo ==================================================
) else (
    echo.
    echo ==================================================
    echo [INFO] Application closed successfully.
    echo ==================================================
)
pause