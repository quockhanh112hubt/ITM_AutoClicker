@echo off
setlocal EnableExtensions

REM Copy Tesseract runtime into project resource folder for portable build.
REM Usage:
REM   copy_tesseract.bat
REM   copy_tesseract.bat "C:\Program Files\Tesseract-OCR"

set "SCRIPT_DIR=%~dp0"
set "DEST_ROOT=%SCRIPT_DIR%resource\tesseract"

if "%~1"=="" (
    set "SRC_ROOT=C:\Program Files\Tesseract-OCR"
) else (
    set "SRC_ROOT=%~1"
)

echo ========================================
echo Copy Tesseract Runtime
echo ========================================
echo Source: %SRC_ROOT%
echo Dest  : %DEST_ROOT%

if not exist "%SRC_ROOT%\tesseract.exe" (
    echo ERROR: tesseract.exe not found in source folder.
    echo Please run with explicit source path, for example:
    echo   copy_tesseract.bat "C:\Program Files\Tesseract-OCR"
    exit /b 1
)

if not exist "%DEST_ROOT%" mkdir "%DEST_ROOT%"
if not exist "%DEST_ROOT%\tessdata" mkdir "%DEST_ROOT%\tessdata"

echo.
echo [1/4] Copying tesseract.exe...
copy /Y "%SRC_ROOT%\tesseract.exe" "%DEST_ROOT%\" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy tesseract.exe
    exit /b 1
)

echo.
echo [2/4] Copying required DLLs...
for %%F in ("%SRC_ROOT%\*.dll") do (
    copy /Y "%%~fF" "%DEST_ROOT%\" >nul
)

echo.
echo [3/4] Copying tessdata...
xcopy "%SRC_ROOT%\tessdata" "%DEST_ROOT%\tessdata\" /E /I /Y >nul
if errorlevel 1 (
    echo ERROR: Failed to copy tessdata folder.
    exit /b 1
)

echo.
echo [4/4] Validating key files...
if not exist "%DEST_ROOT%\tesseract.exe" (
    echo ERROR: Missing %DEST_ROOT%\tesseract.exe
    exit /b 1
)
if not exist "%DEST_ROOT%\tessdata\eng.traineddata" (
    echo WARNING: eng.traineddata not found.
)
if not exist "%DEST_ROOT%\tessdata\vie.traineddata" (
    echo WARNING: vie.traineddata not found. Vietnamese OCR may not work.
)

echo.
echo Done. Portable OCR files copied to:
echo   %DEST_ROOT%
echo.
echo Next step: run build.bat to include OCR into your exe.
exit /b 0

