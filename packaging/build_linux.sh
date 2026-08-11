#!/usr/bin/env bash
# Builds a single-file HOI4MusicPlayer binary (Linux). Run from anywhere -
# it cds to the repo root itself. Needs python3-tk installed system-wide
# (e.g. `sudo apt install python3-tk`) since PyInstaller bundles your
# system Tcl/Tk, it does not ship its own.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet pyinstaller

pyinstaller --noconfirm --clean --onefile --windowed \
    --name HOI4MusicPlayer \
    --icon assets/icon.png \
    --collect-data customtkinter \
    run.py

echo
echo "Build complete: dist/HOI4MusicPlayer"
