@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Keymouse
echo ============================================================
echo   Keymouse - mouse look from your keyboard
echo ============================================================
echo.

REM ---------------------------------------------------------------
REM  1. Find a working Python that also has tkinter (needed for GUI)
REM ---------------------------------------------------------------
set "PYCMD="
set "PYARGS="

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import tkinter" >nul 2>nul
    if not errorlevel 1 ( set "PYCMD=py" & set "PYARGS=-3" )
)
if defined PYCMD goto :runapp

where python >nul 2>nul
if not errorlevel 1 (
    python -c "import tkinter" >nul 2>nul
    if not errorlevel 1 set "PYCMD=python"
)
if defined PYCMD goto :runapp

where python3 >nul 2>nul
if not errorlevel 1 (
    python3 -c "import tkinter" >nul 2>nul
    if not errorlevel 1 set "PYCMD=python3"
)
if defined PYCMD goto :runapp

call :scan_installed
if defined PYCMD goto :runapp

REM ---------------------------------------------------------------
REM  2. No usable Python - install it automatically
REM ---------------------------------------------------------------
echo [*] Python with tkinter was not found on this machine.
echo [*] Installing it now - this can take a minute or two.
echo.
where winget >nul 2>nul
if not errorlevel 1 goto :winget
goto :download

:winget
echo [*] Using winget to install Python 3.12...
winget install --id Python.Python.3.12 --exact --silent --accept-package-agreements --accept-source-agreements >nul 2>nul
if not errorlevel 1 goto :recheck
echo [!] winget install failed - falling back to direct download.
goto :download

:download
set "DLURL=https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
set "INST=%TEMP%\python-3.12.8-amd64.exe"
echo [*] Downloading the Python installer...
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%DLURL%' -OutFile '%INST%' } catch { exit 1 }"
if errorlevel 1 (
    echo [!] Download failed. Install Python manually from:
    echo     https://www.python.org/downloads/
    echo     (tick "Add python.exe to PATH") then run this file again.
    goto :endfail
)
echo [*] Running the installer silently...
start /wait "" "%INST%" /quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_test=0 SimpleInstall=1
del "%INST%" 2>nul

REM ---------------------------------------------------------------
REM  3. Re-locate Python after a fresh install
REM ---------------------------------------------------------------
:recheck
set "PYCMD="
call :scan_installed
if defined PYCMD goto :verified
echo [!] Python was installed but could not be located yet.
echo     It will be ready the next time. Press a key, then run this again.
set /p "x=Press any key..."
exit /b 1

:verified
%PYCMD% %PYARGS% -c "import tkinter" >nul 2>nul
if not errorlevel 1 goto :runapp
echo [!] Python works but tkinter is missing.
echo     Reinstall Python and tick the "tcl/tk and IDLE" feature.
goto :endfail

REM ---------------------------------------------------------------
REM  4. Run Keymouse
REM ---------------------------------------------------------------
:runapp
if exist requirements.txt (
    echo [*] Installing additional requirements...
    %PYCMD% %PYARGS% -m pip install -r requirements.txt >nul 2>nul
)
echo [+] Python ready. Starting Keymouse...
echo.
%PYCMD% %PYARGS% keymouse.py
set "RC=!ERRORLEVEL!"
if not "!RC!"=="0" (
    echo.
    echo [!] Keymouse closed with an error, see the output above.
    pause
)
exit /b !RC!

REM ---------------------------------------------------------------
REM  Subroutine: look in the common per-user / system install spots
REM ---------------------------------------------------------------
:scan_installed
if not defined PYCMD for /D %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if not defined PYCMD if exist "%%~D\python.exe" (
        "%%~D\python.exe" -c "import tkinter" >nul 2>nul
        if not errorlevel 1 set "PYCMD="%%~D\python.exe""
    )
)
if not defined PYCMD for /D %%D in ("%ProgramFiles%\Python3*" "%ProgramFiles(x86)%\Python3*") do (
    if not defined PYCMD if exist "%%~D\python.exe" (
        "%%~D\python.exe" -c "import tkinter" >nul 2>nul
        if not errorlevel 1 set "PYCMD="%%~D\python.exe""
    )
)
exit /b 0

:endfail
echo.
set /p "x=Press any key to exit..."
exit /b 1