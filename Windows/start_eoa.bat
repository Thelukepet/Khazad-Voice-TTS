@echo off
:: Change working directory to the project root
cd /d "%~dp0.."

title KHAZAD VOICE - ECHOES OF ANGMAR
color 0E

:: Check Environment (removed ..\)
if not exist venv (
    echo [ERROR] 'venv' not found. Please run install.bat.
    pause
    exit
)

echo [INFO] Starting Echoes of Angmar Mode...
echo.
echo   1. Echoes Mode
echo   2. Echoes Mode + Voice Mix [Experimental]
echo.
set /p choice="Enter choice (1 or 2): "

if "%choice%"=="2" (
    echo [INFO] Starting Echoes Mode with Voice Mix...
    call venv\Scripts\activate.bat
    python main.py --mode echoes --voice-mix
) else (
    echo [INFO] Starting Echoes Mode...
    call venv\Scripts\activate.bat
    python main.py --mode echoes
)
pause
