@echo off
setlocal

REM Move to the folder where this .bat file lives (the repo root)
cd /d "%~dp0"

REM (optional) activate venv if you use one
IF EXIST ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
)

REM Run your YouTube stats script (adjust the path if your script lives elsewhere)
python scripts\03_pull_youtube_stats.py

pause