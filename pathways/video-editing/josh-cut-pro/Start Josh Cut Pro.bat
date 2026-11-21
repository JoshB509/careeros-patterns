@echo off
rem Starts Josh Cut Pro with no console window. The helper keeps itself running
rem and opens the Josh Cut Pro window. Running this again just reopens the window.
cd /d "%~dp0"
set KMP_DUPLICATE_LIB_OK=TRUE
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "(Get-Content -Raw E:\Videos\DaJoshiResolve\settings.json | ConvertFrom-Json).python"`) do set "PY=%%P"
if not exist "%PY%" (
  echo Could not find the DaJoshiResolve Python at "%PY%".
  echo Check E:\Videos\DaJoshiResolve\settings.json
  pause
  exit /b 1
)
for %%F in ("%PY%") do set "PYW=%%~dpFpythonw.exe"
if not exist "%PYW%" set "PYW=%PY%"
start "" "%PYW%" "%~dp0helper\dajoshi_cut.py"
