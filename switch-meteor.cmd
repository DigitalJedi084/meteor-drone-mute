@echo off
rem Double-click to pick which Meteor (meteorb) ROM variant VPinMAME loads.
echo.
echo   1  breathing_bass
echo   2  heartbeat
echo   3  invader_march
echo   4  clean     (background muted)
echo   5  original  (stock ROMs)
echo.
set /p n=Pick 1-5:
set v=
if "%n%"=="1" set v=breathing_bass
if "%n%"=="2" set v=heartbeat
if "%n%"=="3" set v=invader_march
if "%n%"=="4" set v=clean
if "%n%"=="5" set v=original
if "%v%"=="" (echo Not a choice. & pause & exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-variant.ps1" %v%
pause
