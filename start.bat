@echo off
cd /d "%~dp0"

python --version > nul 2>&1
if %errorlevel% == 0 (
    python app.py
) else (
    py --version > nul 2>&1
    if %errorlevel% == 0 (
        py app.py
    ) else (
        echo Error: python not found. Please install Python and add it to PATH.
        pause
        exit /b 1
    )
)

pause
