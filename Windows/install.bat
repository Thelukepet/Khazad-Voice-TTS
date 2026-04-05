@echo off
setlocal enabledelayedexpansion

:: Change working directory to the project root so all paths resolve correctly
cd /d "%~dp0.."

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
echo [1/6] Igniting the Forge (Creating Virtual Environment)...
%PYTHON_CMD% -m venv venv
if %errorlevel% neq 0 goto :error

echo [2/6] Stoking the Fires (Activating Environment)...
call venv\Scripts\activate

echo [3/6] Sharpening the Axe (Updating Setup Tools)...
python -m pip install --upgrade pip setuptools wheel
:: Install NLTK immediately to ensure it is present regardless of later conflicts
python -m pip install nltk

echo.
echo ==================================================
echo           SELECT YOUR GPU DRIVER VERSION
echo ==================================================
echo.
echo [1] CUDA 12.1 (Standard - Recommended for most Nvidia Graphics cards)
echo [2] CUDA 12.8 (Nightly - For the latest RTX 50-Series)
echo [3] CPU Only  (Slow - Not recommended for using OmniVoice, will still work with Kokoro)
echo.
set /p choice="Enter selection [1, 2, or 3]: "

if "%choice%"=="1" (
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
) else if "%choice%"=="2" (
    pip install --pre torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
) else (
    pip install torch torchaudio
)
if %errorlevel% neq 0 goto :error

:: --- 3. OmniVoice Setup ---
echo.
echo [4/6] Summoning the Voice (Installing OmniVoice TTS)...

echo Installing OmniVoice package...
pip install omnivoice
if %errorlevel% neq 0 goto :error

:: --- 4. Main Requirements ---
echo.
echo [5/6] Finalizing the Craft (Installing Main Requirements)...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Main requirements reported an error.
    echo This is usually a version conflict. NLTK was pre-installed to ensure safety.
)

:: --- 5. NLTK Data Download ---
echo.
echo [6/6] Teaching the Runes (Downloading NLTK Data)...
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('averaged_perceptron_tagger')"

echo.
echo ==================================================
echo           INSTALLATION COMPLETE!
echo ==================================================
echo The Khazad Voice TTS is ready. Follow the calibrate instructions on the github page.
pause
exit /b

:error
echo.
echo ==================================================
echo [ERROR] The installation failed!
echo Check the error message above.
echo ==================================================
pause
exit /b
