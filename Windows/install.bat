@echo off
setlocal enabledelayedexpansion

:: ---------------------------------------------------------------------------
:: KHAZAD VOICE TTS INSTALLER - AUTOMATED INSTALLATION SCRIPT
::
:: This script automatically installs all required dependencies for Khazad Voice TTS.
:: It handles CUDA detection, Python version selection, and dependency installation.
::
:: Usage: Run this script from the root directory of the project.
:: ---------------------------------------------------------------------------

:: Set the project directory
set "PROJECT_DIR=%CD%"

:: Check if we're in the correct directory
if not exist "voice-tts\voice-tts.py" (
    echo [ERROR] Please run this script from the root directory of the project.
    echo [ERROR] Expected to find 'voice-tts\voice-tts.py' but it doesn't exist.
    pause
    exit /b 1
)

echo ====================================================================
echo KHAZAD VOICE TTS - AUTOMATED INSTALLATION
echo ====================================================================
echo.
echo This script will automatically install all required dependencies.
echo Please wait while we detect your system configuration...
echo.

:: Step 1: Check if Python is installed
echo [1/7] Checking for Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed. Please install Python 3.10 or 3.11.
    echo [INFO] Download from: https://www.python.org/downloads/
    echo [INFO] Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Get Python version and path
for /f "tokens=*" %%i in ('python -c "import sys; print(sys.version)"') do set "PYTHON_VERSION=%%i"
for /f "tokens=*" %%i in ('python -c "import sys; print(sys.executable)"') do set "PYTHON_PATH=%%i"

echo [INFO] Python detected: !PYTHON_VERSION!
echo [INFO] Python path: !PYTHON_PATH!

:: Step 2: Detect CUDA availability
echo [2/7] Detecting CUDA availability...
set "CUDA_AVAILABLE=0"

:: Check for CUDA by trying to import torch and checking cuda availability
python -c "import torch; print(torch.cuda.is_available())" >nul 2>&1
if errorlevel 1 (
    echo [INFO] CUDA not detected or PyTorch not installed.
    echo [INFO] Will install CPU version of PyTorch.
    set "CUDA_AVAILABLE=0"
) else (
    python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
    if errorlevel 1 (
        echo [INFO] PyTorch installed but CUDA not available.
        echo [INFO] Will install CPU version of PyTorch.
        set "CUDA_AVAILABLE=0"
    ) else (
        echo [SUCCESS] CUDA detected!
        set "CUDA_AVAILABLE=1"
    )
)

:: Step 3: Detect NVIDIA GPU
echo [3/7] Detecting NVIDIA GPU...
set "NVIDIA_GPU=0"

:: Check for NVIDIA GPU using nvidia-smi or torch
python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
if errorlevel 1 (
    echo [INFO] No NVIDIA GPU detected.
    echo [INFO] Will use CPU processing.
    set "NVIDIA_GPU=0"
) else (
    echo [SUCCESS] NVIDIA GPU detected!
    set "NVIDIA_GPU=1"
)

:: Step 4: Select requirements file
echo [4/7] Selecting requirements file...
set "REQ_FILE=requirements.txt"

if "!CUDA_AVAILABLE!"=="1" (
    echo [INFO] CUDA available.
    if "!NVIDIA_GPU!"=="1" (
        echo [INFO] NVIDIA GPU detected.
        if exist "requirements_nvidia.txt" (
            set "REQ_FILE=requirements_nvidia.txt"
            echo [INFO] Using NVIDIA requirements.
        ) else (
            set "REQ_FILE=requirements_cuda.txt"
            echo [INFO] Using CUDA requirements.
        )
    ) else (
        set "REQ_FILE=requirements_cuda.txt"
        echo [INFO] Using CUDA requirements.
    )
) else (
    echo [INFO] No CUDA detected.
    set "REQ_FILE=requirements.txt"
    echo [INFO] Using standard requirements.
)

:: Step 5: Install NLTK (pre-install to avoid version conflicts)
echo [5/7] Installing NLTK (pre-install)...
"%PYTHON%" -m pip install nltk==3.9.1 -q
if errorlevel 1 (
    echo [WARNING] NLTK installation failed.
    echo [INFO] This is usually a version conflict. NLTK was pre-installed to ensure safety.
) else (
    echo [SUCCESS] NLTK installed successfully.
)

:: Step 6: Install main requirements
echo [6/7] Installing main requirements...
"%PYTHON%" -m pip install -r "%CD%\requirements.txt" -q
if errorlevel 1 (
    echo [WARNING] Main requirements reported an error.
    echo [INFO] This is usually a version conflict. NLTK was pre-installed to ensure safety.
    echo [INFO] Please check the requirements.txt file and install manually if needed.
) else (
    echo [SUCCESS] Main requirements installed successfully.
)

:: Step 7: Install CUDA-specific requirements (if applicable)
if "!CUDA_AVAILABLE!"=="1" (
    echo [7/7] Installing CUDA-specific requirements...
    "%PYTHON%" -m pip install -r "%CD%\requirements_cuda.txt" -q
    if errorlevel 1 (
        echo [WARNING] CUDA requirements reported an error.
        echo [INFO] This is usually a version conflict. Please check the requirements_cuda.txt file.
        echo [INFO] You may need to install CUDA-specific packages manually.
    ) else (
        echo [SUCCESS] CUDA requirements installed successfully.
    )
) else (
    echo [7/7] Skipping CUDA-specific requirements (CUDA not available).
)

:: Installation complete
echo.
echo ====================================================================
echo INSTALLATION COMPLETE!
echo ====================================================================
echo.
echo Summary:
echo -
