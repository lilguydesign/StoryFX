@echo off
taskkill /IM adb.exe /F

"C:\Tools\ADB_StoryFX\adb.exe" kill-server
"C:\Tools\ADB_StoryFX\adb.exe" start-server

echo ADB StoryFX (5038) actif !
pause
