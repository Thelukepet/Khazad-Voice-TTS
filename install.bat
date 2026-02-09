@echo off
title KHAZAD VOICE TTS - UV INSTALLER
color 0B

echo ==========================================================
echo                 KHAZAD VOICE TTS
echo      "Baruk Khazad! The Voice of the Dwarves is upon you!"
echo ==========================================================
echo.

:: --- 1. CHECK & INSTALL UV ---
echo [1/6] Checking for 'uv' (The ultra-fast installer)...

:: Define fallback paths where uv might hide
set "UV_PATH_1=%USERPROFILE%\.cargo\bin\uv.exe"
set "UV_PATH_2=%LOCALAPPDATA%\uv\uv.exe"
set "UV_PATH_3=%USERPROFILE%\.local\bin\uv.exe"

:: Check if uv is already globally available
uv --version >nul 2>&1
if %errorlevel%==0 (
    set "UV_CMD=uv"
    goto :uv_found
)

:: Check known paths
if exist "%UV_PATH_1%" set "UV_CMD=%UV_PATH_1%" & goto :uv_found
if exist "%UV_PATH_2%" set "UV_CMD=%UV_PATH_2%" & goto :uv_found
if exist "%UV_PATH_3%" set "UV_CMD=%UV_PATH_3%" & goto :uv_found

:: If not found, INSTALL IT
echo [INFO] 'uv' not found. Installing it now...
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

:: Re-check paths after install
if exist "%UV_PATH_1%" set "UV_CMD=%UV_PATH_1%" & goto :uv_found
if exist "%UV_PATH_2%" set "UV_CMD=%UV_PATH_2%" & goto :uv_found
if exist "%UV_PATH_3%" set "UV_CMD=%UV_PATH_3%" & goto :uv_found

:: Fallback if auto-detection fails completely
echo [WARNING] Could not locate uv.exe automatically.
echo Please restart this window or add uv to your PATH manually.
pause
exit /b

:uv_found
echo [INFO] uv is ready at: "%UV_CMD%"

:: --- 2. CREATE VENV ---
echo.
echo [2/6] Forging the Environment...
:: --allow-existing: Updates the venv if it exists (No "Are you sure?" prompt)
:: --python 3.12: Ensures we are on the correct version
"%UV_CMD%" venv venv --python 3.12 --allow-existing

:: Activate it so subsequent commands know where to install
call venv\Scripts\activate

:: --- 3. GPU SELECTION ---
echo.
echo ==================================================
echo           SELECT YOUR GPU DRIVER VERSION
echo ==================================================
echo [1] CUDA 12.1 (Standard - Recommended for most Nvidia cards)
echo [2] CUDA 12.8 (Nightly  - For RTX 50-Series)
echo [3] CPU Only  (Slow     - Not recommended for LuxTTS)
echo.
set /p choice="Enter selection [1, 2, or 3]: "

echo.
echo [3/6] Installing PyTorch...
if "%choice%"=="1" (
    echo [INFO] Installing Stable CUDA 12.1...
    "%UV_CMD%" pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
) else if "%choice%"=="2" (
    echo [INFO] Installing Nightly CUDA 12.8...
    "%UV_CMD%" pip install --pre torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
) else (
    echo [INFO] Installing CPU Version...
    "%UV_CMD%" pip install torch torchaudio
)

:: --- 4. LUXTTS SETUP ---
echo.
echo [4/6] Setting up LuxTTS...

if not exist "LuxTTS" (
    echo [INFO] Cloning LuxTTS...
    git clone -b main https://github.com/Thelukepet/LuxTTS.git
) else (
    echo [INFO] Updating LuxTTS...
    cd LuxTTS
    git pull origin main
    cd ..
)

echo [INFO] Installing LuxTTS Dependencies...
"%UV_CMD%" pip install -r LuxTTS\requirements.txt

echo [INFO] Installing LuxTTS Package...
:: --no-deps prevents it from overwriting the Torch version we just installed
"%UV_CMD%" pip install --no-deps -e LuxTTS

:: --- 5. MAIN REQUIREMENTS ---
echo.
echo [5/6] Installing Main Requirements...
"%UV_CMD%" pip install -r requirements.txt
:: Explicitly install extra tools just in case
"%UV_CMD%" pip install gradio

:: --- 6. NLTK DATA ---
echo.
echo [6/6] Teaching the Runes (Downloading NLTK Data)...
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('averaged_perceptron_tagger')"

echo.
echo ==================================================
echo           INSTALLATION COMPLETE!
echo ==================================================
echo The Khazad Voice TTS is ready.
pause