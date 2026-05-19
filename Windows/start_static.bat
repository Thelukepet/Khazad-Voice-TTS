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
call venv\Scripts\activate.bat
python main.py --mode static
pause
