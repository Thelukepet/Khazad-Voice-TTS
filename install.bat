@echo off
title KHAZAD VOICE TTS - INSTALLER
color 0E

echo ==========================================================
echo                 KHAZAD VOICE TTS
echo      "Baruk Khazad! The Voice of the Dwarves is upon you!"
echo ==========================================================
echo.

:: --- 1. Tool Checks (Git & Python) ---

:: Check for Git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed.
    echo The Khazad cannot work without their tools.
    pause
    exit
)

:: Try to find Python 3.12 (preferred) or fallback to system python
set PYTHON_CMD=python
py -3.12 --version >nul 2>&1
if %errorlevel%==0 (
    echo [INFO] Found Python 3.12 via launcher.
    set PYTHON_CMD=py -3.12
) else (
    :: Fallback check
    python --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] Python is not installed or not in PATH.
        echo Please install Python 3.12 and tick "Add to PATH".
        pause
        exit
    )
)

echo [INFO] Using Python: %PYTHON_CMD%
echo.
echo [1/5] Igniting the Forge (Creating Virtual Environment)...
%PYTHON_CMD% -m venv venv

echo [2/5] Stoking the Fires (Activating Environment)...
call venv\Scripts\activate

echo [3/5] Sharpening the Axe (Updating Setup Tools)...
python -m pip install --upgrade pip setuptools wheel

echo.
echo ==================================================
echo           SELECT YOUR GPU DRIVER VERSION
echo ==================================================
echo.
echo [1] CUDA 12.1 (Standard - Recommended for most Nvidia Graphics cards)
echo [2] CUDA 12.8 (Nightly - For the latest RTX 50-Series)
echo [3] CPU Only  (Slow - Not recommended for using LuxTTS, will still work with Kokoro)
echo.
set /p choice="Enter selection [1, 2, or 3]: "

if "%choice%"=="1" (
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
) else if "%choice%"=="2" (
    pip install --pre torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
) else (
    pip install torch torchaudio
)

:: --- 3. LuxTTS Setup ---
echo.
echo [4/5] Summoning the Voice (Setting up LuxTTS)...

if not exist "LuxTTS" (
    echo [INFO] LuxTTS not found. Cloning the 'main' branch...
    :: Added -b main to ensure we get the right branch immediately
    git clone -b main https://github.com/Thelukepet/LuxTTS.git
) else (
    echo [INFO] LuxTTS exists. Updating the scrolls...
    cd LuxTTS
    :: Fetch all updates and force-switch to main if it's currently on master
    git fetch origin
    git checkout main
    git pull origin main
    cd ..
)

echo Installing LuxTTS dependencies...
pip install -r LuxTTS\requirements.txt
pip install -e LuxTTS

:: --- 4. Main Requirements ---
echo.
echo [5/5] Finalizing the Craft (Installing Main Requirements)...
pip install -r requirements.txt

echo.
echo ==================================================
echo           INSTALLATION COMPLETE!
echo ==================================================
echo The Khazad Voice TTS is ready. Run "start.bat" to begin.
pause