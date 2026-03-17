@echo off
:: Change working directory to the project root
cd /d "%~dp0.."

title KHAZAD VOICE - ECHOES OF ANGMAR
color 0E

:: Check Environment (removed ..\)
if not exist venv (
    echo [ERROR] 'venv' not found. Please run install.bat.
    pause
    exit
)

echo [INFO] Starting Echoes of Angmar Mode...
:: Launch commands (removed ..\)
call venv\Scripts\activate.bat
python main.py --mode echoes
pause