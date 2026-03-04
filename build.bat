@echo off
setlocal

REM ITM AutoClicker build script
REM Update this version for each release
set APP_NAME=ITM_AutoClicker
set APP_VERSION=1.0.5
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
echo [1/6] Installing requirements...
%PYTHON% -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    exit /b 1
)

echo.
echo [2/6] Preparing bundled OCR engine...
if not exist "resource\tesseract\tesseract.exe" (
    if exist "copy_tesseract.bat" (
        call copy_tesseract.bat
    )
)
if not exist "resource\tesseract\tesseract.exe" (
    echo WARNING: resource\tesseract\tesseract.exe not found.
    echo OCR may not work on machines without local Tesseract installation.
) else (
    echo Found bundled OCR: resource\tesseract\tesseract.exe
)

echo.
echo [3/6] Ensuring PyInstaller is installed...
%PYTHON% -m pip install -q pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install or run PyInstaller.
    exit /b 1
)

echo.
echo [4/6] Cleaning old build folders...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

echo.
echo [5/6] Building one-file executable...
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "%APP_NAME%" ^
  --icon "resource\Icon.ico" ^
  --add-data "qt.conf;." ^
  --add-data "resource;resource" ^
  "%ENTRYPOINT%"
if errorlevel 1 (
    echo ERROR: Build failed.
    exit /b 1
)

echo.
echo [6/6] Renaming artifact with version...
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
