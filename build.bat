@echo off
title MHW Food Loadouts - Builder
color 0A

echo ================================================
echo   MHW Food Loadouts - Build Script
echo ================================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python from python.org
    echo         and make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
python -m pip install --quiet --upgrade PyQt5 psutil pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo       Done.
echo.

echo [2/3] Cleaning previous build...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist "MHW Food Loadouts.spec" del /q "MHW Food Loadouts.spec"
echo       Done.
echo.

echo [3/3] Building .exe...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "MHW Food Loadouts" ^
    --hidden-import=winreg ^
    --hidden-import=psutil ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See output above for details.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Build successful!
echo ================================================
echo.
echo   Your .exe is here:
echo   %~dp0dist\MHW Food Loadouts.exe
echo.
echo   Copy these into the same folder as the .exe:
echo     - MonsterHunterWorld.CT
echo     - MHW_Bridge.lua  (paste into CE Lua script)
echo.

:: Offer to open the dist folder
set /p OPEN="Open dist folder now? (y/n): "
if /i "%OPEN%"=="y" explorer "%~dp0dist"

pause
