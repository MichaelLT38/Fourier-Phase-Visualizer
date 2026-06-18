@echo off
setlocal

if not exist dist\FourierDragApp\FourierDragApp.exe (
  echo App executable not found. Building it first...
  call build.bat
  if errorlevel 1 goto :error
)

where iscc >nul 2>nul
if errorlevel 1 (
  if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
  ) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
  ) else if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
    set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
  ) else (
    echo Inno Setup was not found.
    echo Install it from: https://jrsoftware.org/isdl.php
    echo Then rerun: make-installer.bat
    exit /b 1
  )
) else (
  for /f "delims=" %%I in ('where iscc') do (
    set "ISCC=%%I"
    goto :found
  )
)

:found
"%ISCC%" installer\FourierDragApp.iss
if errorlevel 1 goto :error

echo.
echo Installer build complete.
echo Share this file:
echo   installer\Output\FourierDragApp-Setup.exe
exit /b 0

:error
echo.
echo Installer build failed.
exit /b 1
