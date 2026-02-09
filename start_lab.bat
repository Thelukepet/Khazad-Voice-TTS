@echo off
title KHAZAD VOICE LAB
color 0B

if not exist venv (
    echo [ERROR] Virtual environment not found. Run install.bat first.
    pause
    exit
)

echo [INFO] Activating environment...
call venv\Scripts\activate

echo [INFO] Installing/Checking Gradio (UI)...
pip install gradio -q

echo.
echo [INFO] Starting Voice Lab...
echo [INFO] A browser window should open shortly.
python voice_lab.py

pause