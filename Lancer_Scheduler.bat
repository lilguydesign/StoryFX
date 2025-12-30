@echo off
title StoryFX Scheduler
cd /d "%~dp0"

echo.
echo [StoryFX] Lancement du Scheduler...
echo.

REM -- Lancer scheduler.py dans une nouvelle fenêtre indépendante
start "StoryFX Scheduler" "%~dp0storyfx\.venv\Scripts\python.exe" "%~dp0storyfx\scheduler.py"
