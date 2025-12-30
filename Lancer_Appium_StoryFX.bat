@echo off
title Appium StoryFX

set ANDROID_ADB_SERVER_PORT=5038
set PATH=C:\Tools\ADB_StoryFX;%PATH%

appium --allow-cors --relaxed-security --base-path /wd/hub --port 4723

pause
