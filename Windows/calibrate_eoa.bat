@echo off
cd /d "%~dp0.."

title CALIBRATE - ECHOES OF ANGMAR
call venv\Scripts\activate.bat
python main.py --calibrate echoes
pause
