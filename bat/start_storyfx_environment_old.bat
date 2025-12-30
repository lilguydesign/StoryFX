@echo off
chcp 65001 >nul

echo ===============================================================
echo 🔥 STORYFX - RESET & AUTO-CONFIG ENVIRONNEMENT (ADB + APPIUM)
echo ===============================================================

echo.
echo [1] 🔄 Suppression variable ANDROID_ADB_SERVER_PORT (user + system)
setx ANDROID_ADB_SERVER_PORT "" >nul
setx ANDROID_ADB_SERVER_PORT "" /M >nul

echo [1b] 🔄 Suppression dans le registre (toutes localisations Windows)
reg delete "HKCU\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1
reg delete "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1
reg delete "HKLM\SYSTEM\ControlSet001\Control\Session Manager\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1
reg delete "HKU\.DEFAULT\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1
reg delete "HKU\S-1-5-18\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1
reg delete "HKU\S-1-5-19\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1
reg delete "HKU\S-1-5-20\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1

echo.
echo [2] 🔪 Kill ADB + Node + Appium serveurs
taskkill /IM adb.exe /F >nul 2>&1
taskkill /IM node.exe /F >nul 2>&1

echo.
echo [3] 🚀 Redémarrage ADB Android Studio (PORT 5037)
"C:\Users\lilgu\AppData\Local\Android\Sdk\platform-tools\adb.exe" kill-server
"C:\Users\lilgu\AppData\Local\Android\Sdk\platform-tools\adb.exe" start-server

echo.
echo    - Vérification du port ADB Android Studio :
netstat -ano | findstr :5037

echo.
echo [4] 🚀 Activation ADB StoryFX (PORT 5038)
set ANDROID_ADB_SERVER_PORT=5038
"C:\Tools\ADB_StoryFX\adb.exe" kill-server
"C:\Tools\ADB_StoryFX\adb.exe" start-server

echo.
echo    - Vérification du port StoryFX :
netstat -ano | findstr :5038

echo.
echo [5] 🚀 Lancement APPIUM configuré pour utiliser ADB StoryFX
start "" appium --allow-cors --relaxed-security --base-path /wd/hub --port 4723 --adb-port 5038

echo.
echo [6] ⏳ Attente du démarrage APPIUM (2 sec)...
timeout /t 2 >nul

echo.
echo    - Vérification du port Appium :
netstat -ano | findstr :4723

echo.
echo ===============================================================
echo ✅ ENVIRONNEMENT STORYFX PRÊT (ADB 5037 + ADB 5038 + APPIUM 4723)
echo ===============================================================

pause
