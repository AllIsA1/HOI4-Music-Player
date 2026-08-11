@echo off
REM Builds a single-file HOI4MusicPlayer.exe (Windows). Run from the repo root
REM or from this build/ folder - it figures out the project root either way.
setlocal
cd /d "%~dp0\.."

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet pyinstaller

pyinstaller --noconfirm --clean --onefile --windowed ^
    --name HOI4MusicPlayer ^
    --icon assets\icon.ico ^
    --collect-data customtkinter ^
    run.py

echo.
echo Build complete: dist\HOI4MusicPlayer.exe
endlocal
