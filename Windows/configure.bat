@echo off
cd /d "%~dp0.."

title KHAZAD VOICE - CONFIGURATION & LAB
color 0B

echo ==========================================================
echo              KHAZAD VOICE CONFIGURATION
echo    "Forge your settings. Config your settings for CPU or GPU."
echo ==========================================================
echo.

if not exist venv (
    echo [ERROR] Virtual environment not found. Run install.bat first.
    pause
    exit
)

:: --- 1. CHECK FFMPEG (Required for Whisper/Audio Processing) ---
echo [INFO] Checking for FFmpeg...
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [CRITICAL] FFmpeg is missing!
    echo The Voice Lab requires FFmpeg to process audio files.
    echo.
    set /p install_choice="Install FFmpeg automatically via Winget? (y/n): "
    if /i "!install_choice!"=="y" (
        winget install -e --id Gyan.FFmpeg
        if %errorlevel% neq 0 (
            echo [ERROR] Install failed. Please install FFmpeg manually.
            pause
            exit
        )
        echo.
        echo [IMPORTANT] FFmpeg installed. Please RESTART this script.
        pause
        exit
    ) else (
        echo Please install FFmpeg manually.
        pause
        exit
    )
)

echo [OK] FFmpeg found.

:: --- 2. LAUNCH APP ---
echo [INFO] Activating environment...
call venv\Scripts\activate

echo.
echo [INFO] Ensuring Lab Dependencies are installed...
:: We install gradio here to ensure the config UI works even if they skipped it before
pip install gradio openai-whisper soundfile -q

echo.
echo [INFO] Starting Configuration Suite...
python voice_lab.py

if %errorlevel% neq 0 pause