@echo off
where python >nul 2>nul
if errorlevel 1 (
    echo Python is not installed or not on PATH.
    pause
    exit /b 1
)

python -m pip install --upgrade pyinstaller >nul
python -m PyInstaller --noconfirm --onedir --windowed --icon=icon.ico --add-data "icon.ico;." --name "Image Converter" main_gui.py

echo.
echo Done. The app is in dist\Image Converter\
echo Share the whole folder, not just the exe.
pause
