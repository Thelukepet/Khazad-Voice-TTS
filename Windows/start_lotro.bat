@echo off
cd /d "%~dp0.."

title KHAZAD VOICE - RETAIL MODE
color 0E

:: Check Environment
if not exist venv (
    echo [ERROR] 'venv' not found. Please run install.bat.
    pause
    exit
)

echo [INFO] Starting Retail Mode...
echo.
echo   1. Retail Mode
echo   2. Retail Mode + Voice Mix [Experimental]
echo.
set /p choice="Enter choice (1 or 2): "

if "%choice%"=="2" (
    echo [INFO] Starting Retail Mode with Voice Mix...
    call venv\Scripts\activate.bat
    python main.py --mode retail --voice-mix
) else (
    echo [INFO] Starting Retail Mode...
    call venv\Scripts\activate.bat
    python main.py --mode retail
)
pause
