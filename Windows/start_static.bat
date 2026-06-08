@echo off
cd /d "%~dp0.."

title KHAZAD VOICE - STATIC MODE
color 0E

:: Check Environment
if not exist venv (
    echo [ERROR] 'venv' not found. Please run install.bat.
    pause
    exit
)

echo [INFO] Starting Static Mode...
echo.
echo   1. Static Mode
echo   2. Static Mode + Voice Mix [Experimental]
echo.
set /p choice="Enter choice (1 or 2): "

if "%choice%"=="2" (
    echo [INFO] Starting Static Mode with Voice Mix...
    call venv\Scripts\activate.bat
    python main.py --mode static --voice-mix
) else (
    echo [INFO] Starting Static Mode...
    call venv\Scripts\activate.bat
    python main.py --mode static
)
pause
