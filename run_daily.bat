@echo off
cd /d "%~dp0"
echo [System] Starting Automation Pipeline...

:: 1. Activate venv
call venv\Scripts\activate

:: 2. Run Main Script
python main.py

:: 3. Finish
echo.
echo [System] Task Completed.
pause
