@echo off
cd /d "%~dp0.."

title CALIBRATE - RETAIL
call venv\Scripts\activate.bat
python main.py --calibrate retail
pause
