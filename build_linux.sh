#!/bin/bash
cd "$(dirname "$0")"
echo "Building Sync EverDrive GB X7 for Linux..."

# Check if virtual environment exists, if not try to create one
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating .venv..."
    if command -v uv &> /dev/null; then
        uv venv .venv
    else
        python3 -m venv .venv
    fi
fi

# Activate the virtual environment
if [ -f ".venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Install requirements
if command -v uv &> /dev/null; then
    echo "Installing requirements with uv..."
    uv pip install -r requirements.txt pyinstaller
else
    echo "Installing requirements with pip..."
    python3 -m pip install -r requirements.txt pyinstaller
fi

echo "Running PyInstaller..."
pyinstaller --clean --noconfirm sync_everdrive.spec

echo "Build complete! Your executable is located in the 'dist' folder."
