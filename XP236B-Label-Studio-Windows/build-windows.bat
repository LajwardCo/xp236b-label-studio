@echo off
REM ============================================================
REM  Build XP-236B Label Studio into a standalone Windows .exe
REM  Run this ONCE on a Windows PC that has Python 3 installed.
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo === Checking for Python ===
where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python is not installed or not on PATH.
  echo Install it from https://www.python.org/downloads/  ^(tick "Add Python to PATH"^),
  echo then run this file again.
  echo.
  pause
  exit /b 1
)

echo.
echo === Installing build dependencies ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 ( echo Dependency install failed. & pause & exit /b 1 )

echo.
echo === Building LabelStudio.exe (this takes a minute) ===
python -m PyInstaller --onedir --name LabelStudio ^
  --collect-data arabic_reshaper ^
  --hidden-import win32print --hidden-import win32ui ^
  --noconfirm server.py
if errorlevel 1 ( echo Build failed. & pause & exit /b 1 )

echo.
echo ============================================================
echo   Done!  Your app is in:  dist\LabelStudio\
echo   Run it with:            dist\LabelStudio\LabelStudio.exe
echo.
echo   To hand it to someone else, zip the whole
echo   dist\LabelStudio  folder and send it.
echo ============================================================
echo.
pause
