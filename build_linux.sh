#!/bin/bash
echo "Building Sync EverDrive GB X7 for Linux..."
echo "Installing requirements..."
pip3 install -r requirements.txt
pip3 install pyinstaller

echo "Running PyInstaller..."
pyinstaller --noconfirm --onedir --windowed --collect-all customtkinter sync_everdrive.py

echo "Build complete! Your executable is located in the 'dist/sync_everdrive' folder."
