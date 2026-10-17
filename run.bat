@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python is not installed or not on PATH.
    echo Get it from https://www.python.org/downloads/ and tick "Add Python to PATH".
    pause
    exit /b 1
)

python -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo Python is missing Tkinter. Re-run the Python installer and keep "tcl/tk" ticked.
    pause
    exit /b 1
)

where pythonw >nul 2>nul
if errorlevel 1 goto console
start "" pythonw main_gui.py %*
exit /b 0

:console
python main_gui.py %*
if errorlevel 1 pause
