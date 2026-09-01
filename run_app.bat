@echo off
REM =======================================================
REM Cross-Platform Dictionary Launcher for Windows
REM =======================================================
echo Starting Dictionary Application...

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python run_gui.py
if errorlevel 1 (
    echo.
    echo Application exited with code %errorlevel%.
    pause
)
