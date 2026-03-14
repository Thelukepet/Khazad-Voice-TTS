@echo off
title CALIBRATE - RETAIL
call ..\venv\Scripts\activate.bat
python ..\src\calibrate_retail.py
pause