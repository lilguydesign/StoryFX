@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Le moteur Python StoryFX doit etre installe dans ce dossier.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "windows-bridge\main.py"
pause
