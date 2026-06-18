@echo off
setlocal

python -m pip install --upgrade pip
if errorlevel 1 goto :error

python -m pip install -r requirements.txt pyinstaller>=6.10 pyinstaller-hooks-contrib>=2025.1
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --clean --onedir --windowed --name FourierDragApp --collect-binaries numpy --collect-data numpy main.py
if errorlevel 1 goto :error

echo.
echo Build complete.
echo Application folder: dist\FourierDragApp
echo Executable: dist\FourierDragApp\FourierDragApp.exe
exit /b 0

:error
echo.
echo Build failed.
exit /b 1
