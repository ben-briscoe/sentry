@echo off
setlocal

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv-windows"
set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  echo Python 3.10+ was not found.
  echo Install Python for Windows, then rerun this script.
  exit /b 1
)

if not exist "%ROOT%release\web\index.html" (
  echo Missing prebuilt browser bundle at "%ROOT%release\web".
  exit /b 1
)

if not exist "%VENV%\Scripts\python.exe" (
  echo Creating Windows virtual environment...
  %PYTHON_CMD% -m venv "%VENV%"
  if errorlevel 1 exit /b 1

  echo Installing Python dependencies...
  "%VENV%\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 exit /b 1
  "%VENV%\Scripts\python.exe" -m pip install -r "%ROOT%apps\api\requirements.txt"
  if errorlevel 1 exit /b 1
)

echo Starting SENTRY bridge server on http://127.0.0.1:8000
pushd "%ROOT%apps\api"
"%VENV%\Scripts\python.exe" -m app.main --host 127.0.0.1 --port 8000 --spa-dir "%ROOT%release\web"
set "EXITCODE=%ERRORLEVEL%"
popd
exit /b %EXITCODE%
