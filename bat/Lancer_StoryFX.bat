@echo off
title StoryFX - Interface
cd /d "%~dp0"

echo.
echo [StoryFX] Démarrage de l'interface...
echo.

REM -- Lancer app.py depuis le venv StoryFX
"%~dp0storyfx\.venv\Scripts\python.exe" "%~dp0storyfx\app.py"
