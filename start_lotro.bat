@echo off
title KHAZAD VOICE TTS - RETAIL LOTRO MODE
color 0E

:: Ensure we run from the correct folder (Fixes Admin/Shortcut issues)
cd /d "%~dp0"

echo ----------------------------------------------------------
echo   [KHAZAD VOICE TTS]  ::  Retail LOTRO Edition
echo ----------------------------------------------------------
echo.

:: 1. CHECK ENV
if exist venv goto :env_ok
echo [ERROR] 'venv' not found. Please run install.bat first.
pause
exit

:env_ok
:: 2. ACTIVATE & FIND TOOLS
call venv\Scripts\activate.bat

:: Find UV (checks global or local)
set "UV_CMD=pip"
where uv >nul 2>&1
if %errorlevel%==0 set "UV_CMD=uv"

:: 3. AUTO-UPDATE (Safe Mode - No Brackets)
echo [UPDATE] Checking for updates...
where git >nul 2>&1
if %errorlevel% neq 0 goto :launch

git fetch origin main >nul 2>&1
git status -uno | find "behind" >nul
if %errorlevel% neq 0 goto :launch

echo [UPDATE] Downloading new version...
git pull origin main
if %errorlevel% neq 0 (
    echo [WARNING] Update failed (Local changes detected). Skipping.
    goto :launch
)

echo [UPDATE] Syncing dependencies...
"%UV_CMD%" pip install -q -r requirements.txt

:launch
:: 4. START
echo.
echo [INFO] Starting Retail Mode...
python main.py --mode retail

if %errorlevel% neq 0 (
    echo.
    echo [CRASH] The application closed with an error.
    pause
) else (
    pause
)