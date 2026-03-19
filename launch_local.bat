@echo off
REM Robot Ross — Local launcher for Windows laptop
REM
REM Before running:
REM   1. Plug in the Huenit arm via USB
REM   2. Open Device Manager > Ports (COM & LPT) to find the COM port
REM   3. Update HUENIT_PORT below if it is not COM3

set HUENIT_PORT=COM3

echo Robot Ross Local Control
echo Serial port: %HUENIT_PORT%
echo.
echo Commands:
echo   python skills\huenit\huenit_draw.py calibrate
echo   python skills\huenit\huenit_write.py "Hello World"
echo   python skills\huenit\huenit_jog_control.py
echo   python skills\robot-ross\bob_ross.py write "Hello World"
echo   python skills\robot-ross\bob_ross.py check
echo.

REM Open an interactive shell with the env var set
cmd /k "set HUENIT_PORT=%HUENIT_PORT% && cd /d %~dp0"
