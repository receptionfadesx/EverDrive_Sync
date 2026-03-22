@echo off
echo Building Sync EverDrive GB X7 for Windows...
echo Installing requirements...
pip install -r requirements.txt
pip install pyinstaller

echo Running PyInstaller...
pyinstaller --noconfirm --onefile --windowed --add-data "assets;assets" --icon assets/icon.ico --collect-all customtkinter sync_everdrive.py

echo Build complete! Your executable is located in the 'dist/sync_everdrive' folder.
pause
