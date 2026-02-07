@echo off
TITLE Khazad-Voice Calibration Tool

echo.
echo =================================================
echo   Khazad-Voice Calibration Tool
echo =================================================
echo.
echo This tool will capture the 5 anchors used in your working logic.
echo Please ensure your game is open and a Quest Window is visible.
echo.

:: Check for Virtual Environment
if exist .venv\Scripts\activate (
    call .venv\Scripts\activate
) else if exist venv\Scripts\activate (
    call venv\Scripts\activate
)

:: Run the script
python calibrate.py

echo.
echo =================================================
echo   Finished. You can close this window.
echo =================================================
pause