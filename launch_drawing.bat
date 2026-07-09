@echo off
echo ========================================
echo  Robot Ross — Drawing Mode
echo  Voice control + Voxtral voice output
echo ========================================
echo.
echo Starting Robot Ross...
echo Speak to give drawing commands.
echo Press Q to quit.
echo.
echo ========================================
echo.

cd /d "%~dp0"

set HUENIT_PORT=COM3

C:\Users\migue\.venv312\Scripts\python.exe skills\robot-ross\chat_ross.py ^
    --no-obs ^
    --engine voxtral ^
    %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Robot Ross failed to start.
    echo Make sure the arm is connected on COM3 and Ollama is running.
    echo.
)

pause
