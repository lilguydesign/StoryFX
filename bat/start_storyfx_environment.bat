@echo off
echo ============================================
echo   RESET ENVIRONNEMENT STORYFX (ADB + APPIUM)
echo ============================================

echo [1] Kill ADB + Node...
taskkill /IM adb.exe /F >nul 2>&1
taskkill /IM node.exe /F >nul 2>&1

echo [2] Start ADB StoryFX (port 5038)...
"C:\Tools\ADB_StoryFX\adb.exe" kill-server
"C:\Tools\ADB_StoryFX\adb.exe" start-server

echo [3] Start Appium Server...
start "" appium --allow-cors --relaxed-security --base-path /wd/hub --port 4723

timeout /t 2 >nul

echo [4] Environment ready!
pause
