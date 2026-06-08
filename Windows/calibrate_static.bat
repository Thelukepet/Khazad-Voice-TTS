@echo off
cd /d "%~dp0.."

title CALIBRATE - STATIC QUEST WINDOW
call venv\Scripts\activate.bat
python main.py --calibrate static
pause
