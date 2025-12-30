@echo off
title StoryFX - Arret complet

echo [StoryFX] Fermeture complete...
echo.

taskkill /IM python.exe /F
taskkill /IM pythonw.exe /F
taskkill /IM adb.exe /F

echo.
echo [StoryFX] Tous les processus ont ete arretes.
echo.
pause


A16
adb disconnect
adb -s R58Y9054K7X tcpip 5557
adb shell ip route
adb connect 192.168.1.88:5557