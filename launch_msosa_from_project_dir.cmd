@echo off
setlocal
cd /d "%~dp0"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM"') do set MONTH=%%i
if not exist "%MONTH%" mkdir "%MONTH%"
set "SIMLOG_DIR=%LOCALAPPDATA%\.magic.systems.of.systems.architect\2022x"
if not exist "%SIMLOG_DIR%\%MONTH%" mkdir "%SIMLOG_DIR%\%MONTH%"
if exist "%SIMLOG_DIR%\simulation.log" del /q "%SIMLOG_DIR%\simulation.log"
set "LOG4J_CONFIGURATION_FILE=%~dp0simulation-log4j2-fixed.xml"
set "JAVA_TOOL_OPTIONS=-Dlog4j2.configurationFile=%~dp0simulation-log4j2-fixed.xml"
set "MSOSA_EXE=%MSOSA_EXE%"
if not defined MSOSA_EXE if exist "C:\Program Files\Magic Systems of Systems Architect\bin\msosa.exe" set "MSOSA_EXE=C:\Program Files\Magic Systems of Systems Architect\bin\msosa.exe"
if not defined MSOSA_EXE if exist "C:\Program Files\No Magic\Cameo Systems Modeler\bin\Cameo Systems Modeler.exe" set "MSOSA_EXE=C:\Program Files\No Magic\Cameo Systems Modeler\bin\Cameo Systems Modeler.exe"
if not defined MSOSA_EXE if exist "C:\Program Files\Cameo Systems Modeler\bin\Cameo Systems Modeler.exe" set "MSOSA_EXE=C:\Program Files\Cameo Systems Modeler\bin\Cameo Systems Modeler.exe"
if not defined MSOSA_EXE (
  echo Could not find an MSOSA/Cameo executable.
  echo Set MSOSA_EXE to the full path of msosa.exe and rerun this launcher.
  exit /b 1
)
start "" /D "%~dp0" "%MSOSA_EXE%"
