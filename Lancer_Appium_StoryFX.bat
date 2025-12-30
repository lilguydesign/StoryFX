@echo off
title Appium StoryFX

REM ADB StoryFX sur port 5038
set ANDROID_ADB_SERVER_PORT=5038
set PATH=C:\Tools\ADB_StoryFX;%PATH%

REM Lancer Appium pour StoryFX
appium --allow-cors --relaxed-security --base-path /wd/hub --port 4723 --adb-port 5038


