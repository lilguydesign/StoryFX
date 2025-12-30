@echo off
taskkill /IM adb.exe /F

"C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe" kill-server
"C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe" start-server

echo ADB USB (5037) actif !
pause
