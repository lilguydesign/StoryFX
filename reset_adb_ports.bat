@echo off
title RESET COMPLET ADB (5037 / 5038)

echo =====================================================
echo 🔥 RESET TOTAL DES PORTS ADB (Fix ADB 5037 / 5038)
echo =====================================================

echo.
echo 📌 1) Suppression variable ANDROID_ADB_SERVER_PORT
setx ANDROID_ADB_SERVER_PORT "" >nul
setx ANDROID_ADB_SERVER_PORT "" /M >nul

echo.
echo 📌 2) Purge complète du registre (toutes les zones possibles)
reg delete "HKCU\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1
reg delete "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1
reg delete "HKU\.DEFAULT\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1
reg delete "HKU\S-1-5-18\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1
reg delete "HKU\S-1-5-19\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1
reg delete "HKU\S-1-5-20\Environment" /v ANDROID_ADB_SERVER_PORT /f >nul 2>&1

echo.
echo 📌 3) Vérification que la variable est supprimée
set ANDROID_ADB_SERVER_PORT
echo (Elle doit être ABSENTE)

echo.
echo 📌 4) Fermeture de TOUS les adb.exe actifs
taskkill /IM adb.exe /F >nul 2>&1

echo.
echo 📌 5) Nettoyage du PATH (ADB StoryFX ne doit PAS passer en premier)
setx PATH "%SystemRoot%\system32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0\;" /M >nul

echo.
echo 📌 6) Redémarrage ADB Android Studio sur port 5037
"C:\Users\lilgu\AppData\Local\Android\Sdk\platform-tools\adb.exe" kill-server
"C:\Users\lilgu\AppData\Local\Android\Sdk\platform-tools\adb.exe" start-server

echo.
echo 📌 7) Vérification du port actif :
netstat -ano | findstr :5037
netstat -ano | findstr :5038

echo.
echo =====================================================
echo ✅ FINI : REDÉMARRE TON PC MAINTENANT
echo =====================================================
pause
