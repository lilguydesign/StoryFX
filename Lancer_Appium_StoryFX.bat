@echo off
setlocal
cd /d %~dp0

echo ==== TEST ENV ====
where node
where npm
where npx
echo ==================

echo.
echo ==== START APPIUM ====
npx appium --allow-cors --relaxed-security --base-path /wd/hub --address 127.0.0.1 --port 4723 --adb-port 5038
echo =====================

echo.
echo Exit code: %errorlevel%
echo.
pause
