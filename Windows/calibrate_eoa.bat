@echo off
cd /d "%~dp0.."

title CALIBRATE - ECHOES OF ANGMAR
call venv\Scripts\activate.bat
python src\calibrate_echoes.py
pause