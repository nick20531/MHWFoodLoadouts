@echo off
title MHW Food Loadouts - Build
color 0A
echo ================================================
echo   MHW Food Loadouts - Standalone Builder
echo ================================================
echo.
python --version >nul 2>&1
if errorlevel 1 ( echo [ERROR] Python not found. & pause & exit /b 1 )
echo [1/3] Installing dependencies...
python -m pip install --quiet --upgrade PyQt5 pyinstaller
if errorlevel 1 ( echo [ERROR] pip failed. & pause & exit /b 1 )
echo       Done.
echo.
echo [2/3] Cleaning old build...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist "MHW Food Loadouts.spec" del /q "MHW Food Loadouts.spec"
echo       Done.
echo.
echo [3/3] Building .exe...
python -m PyInstaller --onefile --windowed --name "MHW Food Loadouts" main.py
if errorlevel 1 ( echo. & echo [ERROR] Build failed. & pause & exit /b 1 )
echo.
echo ================================================
echo   Success! dist\MHW Food Loadouts.exe
echo   No Cheat Engine needed.
echo ================================================
echo.
set /p OPEN="Open dist folder? (y/n): "
if /i "%OPEN%"=="y" explorer "%~dp0dist"
pause
