@echo off
REM ============================================================
REM  Run XP-236B Label Studio directly (no build step).
REM  Needs Python 3 installed. Simplest way to just use it.
REM ============================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get it from https://www.python.org/downloads/
  echo ^(tick "Add Python to PATH"^), then run this again.
  pause
  exit /b 1
)

echo Installing dependencies (first run only)...
python -m pip install --quiet pillow qrcode arabic-reshaper python-bidi pywin32

echo Starting Label Studio... your browser will open shortly.
echo Keep this window open while printing. Close it to quit.
python server.py
pause
