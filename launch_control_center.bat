@echo off
echo ========================================
echo  Robot Ross Control Center
echo ========================================
echo.

cd /d "%~dp0"
set HUENIT_PORT=COM3

if "%ANTHROPIC_API_KEY%"=="" echo WARNING: ANTHROPIC_API_KEY not set - sketch will fail
if "%MISTRAL_API_KEY%"=="" echo WARNING: MISTRAL_API_KEY not set - Voxtral TTS will fail

echo Starting server... browser will open automatically.
echo Keep this window open while drawing. Close it to stop.
echo.

C:\Users\migue\.venv312\Scripts\python.exe control_center.py

pause
