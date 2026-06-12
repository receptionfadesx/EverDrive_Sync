@echo off
cd /d "%~dp0"
echo Building Sync EverDrive GB X7 for Windows...

:: Check if virtual environment exists, if not try to create one
if not exist .venv\ (
    echo Virtual environment not found. Creating .venv...
    where uv >nul 2>nul
    if %errorlevel% equ 0 (
        uv venv .venv
    ) else (
        python -m venv .venv
    )
)

:: Activate the virtual environment
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

:: Install requirements
where uv >nul 2>nul
if %errorlevel% equ 0 (
    echo Installing requirements with uv...
    uv pip install -r requirements.txt pyinstaller
) else (
    echo Installing requirements with pip...
    python -m pip install -r requirements.txt pyinstaller
)

echo Running PyInstaller...
pyinstaller --clean --noconfirm sync_everdrive.spec

echo Build complete! Your executable is located in the 'dist' folder.
pause
