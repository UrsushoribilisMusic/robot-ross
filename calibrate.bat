@echo off
cd /d "%~dp0"
set HUENIT_PORT=COM3
echo ========================================
echo  Robot Ross - Calibration
echo ========================================
echo.
C:\Users\migue\.venv312\Scripts\python.exe skills\robot-ross\bob_ross.py calibrate
pause
