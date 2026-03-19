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
echo --- SETUP ---
echo   python skills\huenit\huenit_draw.py calibrate
echo   python skills\robot-ross\bob_ross.py check
echo.
echo --- WRITE ---
echo   python skills\huenit\huenit_write.py "Hello World"
echo   python skills\huenit\huenit_write.py "Hello" --size 12
echo   python skills\robot-ross\bob_ross.py write "Hello World"
echo   python skills\robot-ross\bob_ross.py write "Hello World" --size 15 --no-voice
echo.
echo --- SHAPES ---
echo   python skills\huenit\huenit_draw.py square
echo   python skills\huenit\huenit_draw.py square 50
echo   python skills\huenit\huenit_draw.py circle 20
echo   python skills\huenit\huenit_draw.py triangle 40
echo   python skills\huenit\huenit_draw.py demo
echo   python skills\robot-ross\bob_ross.py draw square 50
echo   python skills\robot-ross\bob_ross.py draw circle 20
echo.
echo --- SVG ---
echo   python skills\huenit\huenit_svg.py mydesign.svg --size 80
echo   python skills\huenit\huenit_svg.py mydesign.svg --dry-run
echo   python skills\robot-ross\bob_ross.py svg mydesign.svg --size 80
echo.
echo --- IMAGE TO DRAWING ---
echo   python skills\huenit\image_to_svg.py photo.jpg --edges --auto
echo   python skills\robot-ross\bob_ross.py image photo.jpg
echo   python skills\robot-ross\bob_ross.py approve
echo   python skills\robot-ross\bob_ross.py more
echo   python skills\robot-ross\bob_ross.py less
echo   python skills\robot-ross\bob_ross.py cancel
echo.
echo --- AI SKETCH ---
echo   python skills\robot-ross\bob_ross.py sketch "a cat on a bench"
echo   python skills\robot-ross\bob_ross.py sketch "a rocket" --direct
echo.
echo --- MANUAL JOG ---
echo   python skills\huenit\huenit_jog_control.py
echo.
echo --- VOICE TEST ---
echo   python skills\voice\speak.py "Hello I am Robot Ross"
echo.

REM Open an interactive shell with the env var set
cmd /k "set HUENIT_PORT=%HUENIT_PORT% && cd /d %~dp0"
