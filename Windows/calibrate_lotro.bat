@echo off
cd /d "%~dp0.."

title CALIBRATE - RETAIL
call venv\Scripts\activate.bat
python src\calibrate_retail.py
pause