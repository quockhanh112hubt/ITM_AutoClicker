@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 exit /b 1

REM ITM AutoClicker build script
set APP_NAME=ITM_AutoClicker
set ENTRYPOINT=main.py

if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

for /f "usebackq delims=" %%v in (`%PYTHON% -c "from src.app_info import APP_VERSION; print(APP_VERSION)"`) do set APP_VERSION=%%v
if "%APP_VERSION%"=="" (
    echo ERROR: Failed to read APP_VERSION from src.app_info
    exit /b 1
)

echo ========================================
echo Building %APP_NAME% v%APP_VERSION%
echo ========================================

echo Using Python: %PYTHON%

echo.
echo [1/6] Installing requirements...
%PYTHON% -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    exit /b 1
)

echo.
echo [2/6] Preparing bundled OCR and Unity resources...
if not exist "resource\tesseract\tesseract.exe" (
    if exist "copy_tesseract.bat" (
        call copy_tesseract.bat
    )
)

if not exist "resource\unity_bridge\itm_unity_bridge_profiles.dll" (
    echo ERROR: Unity profiles helper DLL is missing.
    echo Run: %PYTHON% tools\build_unity_bridge.py
    exit /b 1
)
if not exist "resource\unity_bridge\itm_unity_mono_v1.dll" (
    echo ERROR: Unity Mono helper DLL is missing.
    echo Run: %PYTHON% tools\build_unity_bridge.py --backend mono
    exit /b 1
)
if not exist "resource\unity_bridge\profiles.json" (
    echo ERROR: Unity profile registry is missing: resource\unity_bridge\profiles.json
    exit /b 1
)
if not exist "resource\unity_bridge\MINHOOK_LICENSE.txt" (
    echo ERROR: Unity helper license is missing: resource\unity_bridge\MINHOOK_LICENSE.txt
    exit /b 1
)
%PYTHON% -c "import json; from pathlib import Path; p=json.loads(Path('resource/unity_bridge/profiles.json').read_text(encoding='utf-8-sig')); assert p.get('version') == 1 and p.get('profiles'), 'Invalid Unity profile registry'"
if errorlevel 1 (
    echo ERROR: Unity profile registry validation failed.
    exit /b 1
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
echo [4/6] Preparing release build folder...
REM Keep native build tools and existing test artifacts. PyInstaller cleans its own cache.
if not exist "build\release" mkdir "build\release"

echo.
echo [5/6] Building one-file executable...
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "%APP_NAME%" ^
  --workpath "build\release" ^
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
    if errorlevel 1 (
        echo ERROR: Could not create the versioned executable.
        exit /b 1
    )
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
