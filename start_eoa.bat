@echo off
title KHAZAD VOICE - ECHOES OF ANGMAR
color 0E

:: Check Environment
if not exist venv (
    echo [ERROR] 'venv' not found. Please run install.bat.
    pause
    exit
)

echo [INFO] Starting Echoes of Angmar Mode...
call venv\Scripts\activate.bat
python main.py --mode echoes
pause