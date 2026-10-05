@echo off
setlocal
set "storyfxLegacy=%~dp0transmission\StoryFX_Transmission_20261003_130046\windows"
if not exist "%storyfxLegacy%\StoryFX.exe" (
  echo Compilation StoryFX introuvable.
  exit /b 1
)
start "StoryFX" /D "%storyfxLegacy%" "%storyfxLegacy%\StoryFX.exe"
endlocal
