@echo off
title KHAZAD VOICE LAB
color 0B

:: Ensure we run from the script folder
cd /d "%~dp0"

echo ==========================================================
echo                 KHAZAD VOICE LAB
echo       "Voice sample tester. Add new voices to Khazad-Voice-TTS"
echo ==========================================================
echo.

if not exist venv (
    echo [ERROR] Virtual environment not found. Run install.bat first.
    pause
    exit
)

:: --- 1. FIND UV (Reuse logic) ---
echo [INFO] Locating 'uv'...
set "UV_CMD=pip"
where uv >nul 2>&1
if %errorlevel%==0 set "UV_CMD=uv"
echo [INFO] Using: "%UV_CMD%"

:: --- 2. CHECK FFMPEG & AUTO-INSTALL ---
echo [INFO] Checking for FFmpeg...
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [CRITICAL] FFmpeg is missing!
    echo Whisper requires FFmpeg to transcribe audio.
    echo.
    echo [OPTION] I can try to install it automatically using Windows Package Manager (Winget).
    echo.

    :: Ask User
    set /p install_choice="Do you want to install FFmpeg now? (y/n): "
    if /i "%install_choice%" neq "y" (
        echo.
        echo Please install FFmpeg manually and restart this script.
        pause
        exit
    )

    echo.
    echo [INFO] Installing FFmpeg via Winget...
    winget install -e --id Gyan.FFmpeg

    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Automated install failed. Please run: 'winget install Gyan.FFmpeg' manually.
        pause
        exit
    )

    echo.
    echo ==========================================================
    echo [IMPORTANT] FFmpeg Installed Successfully!
    echo Windows requires a RESTART of this script to see the new program.
    echo Please close this window and run 'start_voice_lab.bat' again.
    echo ==========================================================
    pause
    exit
)

echo [OK] FFmpeg found.

:: --- 3. ACTIVATE & INSTALL ---
echo [INFO] Activating environment...
call venv\Scripts\activate

echo.
echo [INFO] Checking Lab Dependencies...
"%UV_CMD%" pip install gradio openai-whisper soundfile -q

echo.
echo [INFO] Starting Voice Lab...
python voice_lab.py

if %errorlevel% neq 0 pause