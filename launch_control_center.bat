@echo off
echo ========================================
echo  Robot Ross Control Center
echo ========================================
echo.

cd /d "%~dp0"
set HUENIT_PORT=COM3

if "%ANTHROPIC_API_KEY%"=="" echo WARNING: ANTHROPIC_API_KEY not set - sketch will fail
if "%MISTRAL_API_KEY%"=="" echo WARNING: MISTRAL_API_KEY not set - Voxtral TTS will fail

:: Start the ATF Q&A server (Wiki/Ledger buttons, chat Q&A) in its own window
:: if it isn't already running. Same Ollama daemon as Robot Ross, so this does
:: NOT load the local model twice — see note below.
netstat -ano | findstr ":8771" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo Starting ATF Q^&A Server...
    start "ATF Q&A Server" cmd /k "cd /d C:\Users\migue\atf-review && C:\Users\migue\.venv312\Scripts\python.exe ATF\tools\atf_local_server.py"
) else (
    echo ATF Q^&A Server already running.
)

echo Starting server... browser will open automatically.
echo Keep this window open while drawing. Close it to stop.
echo.

C:\Users\migue\.venv312\Scripts\python.exe control_center.py

pause
