@echo off
setlocal

REM ITM AutoClicker build script
REM Update this version for each release
set APP_NAME=ITM_AutoClicker
set APP_VERSION=1.0.0
set ENTRYPOINT=main.py

echo ========================================
echo Building %APP_NAME% v%APP_VERSION%
echo ========================================

if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

echo Using Python: %PYTHON%

echo.
echo [1/4] Ensuring PyInstaller is installed...
%PYTHON% -m pip install -q pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install or run PyInstaller.
    exit /b 1
)

echo.
echo [2/4] Cleaning old build folders...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

echo.
echo [3/4] Building one-file executable...
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "%APP_NAME%" ^
  --add-data "qt.conf;." ^
  "%ENTRYPOINT%"
if errorlevel 1 (
    echo ERROR: Build failed.
    exit /b 1
)

echo.
echo [4/4] Renaming artifact with version...
if exist "dist\%APP_NAME%.exe" (
    copy /y "dist\%APP_NAME%.exe" "dist\%APP_NAME%_v%APP_VERSION%.exe" >nul
    echo Build complete:
    echo   dist\%APP_NAME%.exe
    echo   dist\%APP_NAME%_v%APP_VERSION%.exe
) else (
    echo ERROR: Output exe not found.
    exit /b 1
)

echo.
echo Done.
endlocal
