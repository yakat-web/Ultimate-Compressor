@echo off
TITLE Ultimate Image Compressor - Build Script
CLS

:: =================================================================
::  Builds both a single-file Portable and a full Installer version.
::  Must be run from the project's root directory.
:: =================================================================

ECHO #############################################################
ECHO #           Building Ultimate Image Compressor            #
ECHO #############################################################
ECHO.

:: --- Define the absolute project root directory ---
SET "ProjectRoot=%~dp0"
IF "%ProjectRoot:~-1%"=="\" SET "ProjectRoot=%ProjectRoot:~0,-1%"

ECHO Project Root Directory is: "%ProjectRoot%"
ECHO.

:: --- 1. Dependency Check Phase ---
ECHO [Phase 1/6] Checking Python and required packages...

:: Check Python availability
python --version > NUL 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO. & ECHO !!! Python not found! Please install Python and add it to PATH. !!!
    pause & exit /b
)
FOR /F "tokens=*" %%V IN ('python --version 2^>^&1') DO ECHO    Found: %%V

:: Check and install pip packages
SET "MISSING_PACKAGES="

pip show Pillow > NUL 2>&1
IF %ERRORLEVEL% NEQ 0 SET "MISSING_PACKAGES=%MISSING_PACKAGES% Pillow"

pip show customtkinter > NUL 2>&1
IF %ERRORLEVEL% NEQ 0 SET "MISSING_PACKAGES=%MISSING_PACKAGES% customtkinter"

pip show pyinstaller > NUL 2>&1
IF %ERRORLEVEL% NEQ 0 SET "MISSING_PACKAGES=%MISSING_PACKAGES% pyinstaller"

IF "%MISSING_PACKAGES%"=="" GOTO :NO_MISSING_PKGS

ECHO    Missing packages detected:%MISSING_PACKAGES%
ECHO    Installing...
pip install%MISSING_PACKAGES%
IF %ERRORLEVEL% NEQ 0 (
    ECHO. & ECHO !!! Package installation failed! Check your internet connection. !!!
    pause & exit /b
)
ECHO    All packages installed successfully.
GOTO :DEPS_CHECK_DONE

:NO_MISSING_PKGS
ECHO    All required packages are already installed.

:DEPS_CHECK_DONE
ECHO.

:: --- 2. Cleanup Phase ---
ECHO [Phase 2/6] Cleaning up previous builds...
IF EXIST "%ProjectRoot%\build" RMDIR /S /Q "%ProjectRoot%\build"
IF EXIST "%ProjectRoot%\dist" RMDIR /S /Q "%ProjectRoot%\dist"
IF EXIST "%ProjectRoot%\compressor.spec" DEL "%ProjectRoot%\compressor.spec" > NUL 2>&1
IF EXIST "%ProjectRoot%\ImageCompressor_Portable.spec" DEL "%ProjectRoot%\ImageCompressor_Portable.spec" > NUL 2>&1
IF EXIST "%ProjectRoot%\InstallerOutput" RMDIR /S /Q "%ProjectRoot%\InstallerOutput"
ECHO    Done.
ECHO.

:: --- 3. Build Portable Version (Single EXE) ---
ECHO [Phase 3/6] Building Portable Version (this may take a moment)...
python -m PyInstaller ^
    --name="ImageCompressor_Portable" ^
    --onefile ^
    --windowed ^
    --icon="%ProjectRoot%\icon.ico" ^
    --add-data "%ProjectRoot%\icon.ico;." ^
    --add-data "%ProjectRoot%\tools;tools" ^
    --add-data "%ProjectRoot%\fonts;fonts" ^
    --paths "%ProjectRoot%\src" ^
    --hidden-import="customtkinter" ^
    --collect-all "customtkinter" ^
    --distpath "%ProjectRoot%\dist\portable" ^
    --workpath "%ProjectRoot%\build" ^
    "%ProjectRoot%\compressor.py"

IF %ERRORLEVEL% NEQ 0 (
    ECHO. & ECHO !!! PORTABLE BUILD FAILED! Please check the output above. !!!
    pause & exit /b
)
ECHO    Portable build successful.
ECHO.

:: --- 4. Build Folder Version (for Installer) ---
ECHO [Phase 4/6] Building Folder Version for the installer...
IF EXIST "%ProjectRoot%\build" RMDIR /S /Q "%ProjectRoot%\build"
IF EXIST "%ProjectRoot%\compressor.spec" DEL "%ProjectRoot%\compressor.spec" > NUL 2>&1
IF EXIST "%ProjectRoot%\ImageCompressor_Portable.spec" DEL "%ProjectRoot%\ImageCompressor_Portable.spec" > NUL 2>&1

python -m PyInstaller ^
    --name="compressor" ^
    --windowed ^
    --icon="%ProjectRoot%\icon.ico" ^
    --add-data "%ProjectRoot%\icon.ico;." ^
    --add-data "%ProjectRoot%\tools;tools" ^
    --add-data "%ProjectRoot%\fonts;fonts" ^
    --paths "%ProjectRoot%\src" ^
    --hidden-import="customtkinter" ^
    --collect-all "customtkinter" ^
    --distpath "%ProjectRoot%\dist" ^
    --workpath "%ProjectRoot%\build" ^
    "%ProjectRoot%\compressor.py"

IF %ERRORLEVEL% NEQ 0 (
    ECHO. & ECHO !!! FOLDER BUILD FAILED! Please check the output above. !!!
    pause & exit /b
)
ECHO    Folder build successful.
ECHO.

:: --- 5. Build Installer using Inno Setup ---
ECHO [Phase 5/6] Building Installer (setup.exe)...
SET "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
IF NOT EXIST "%ISCC_PATH%" (
    ECHO Inno Setup not found at default location: "%ISCC_PATH%"
    pause
    exit /b
)

IF NOT EXIST "%ProjectRoot%\dist\compressor" (
    ECHO. & ECHO !!! CRITICAL ERROR: The 'dist\compressor' directory was not found! !!!
    pause & exit /b
)

ECHO Compiling Inno Setup script...
"%ISCC_PATH%" /DAppRoot="%ProjectRoot%" "%ProjectRoot%\installer\setup.iss"

IF %ERRORLEVEL% NEQ 0 (
    ECHO. & ECHO !!! INSTALLER BUILD FAILED! Please check Inno Setup output. !!!
    pause & exit /b
)
ECHO    Installer build successful.
ECHO.

:: --- 6. Final Packaging ---
ECHO [Phase 6/6] Packaging final release files...

:: Use project RELEASE folder
SET "RELEASE=%ProjectRoot%\RELEASE"
IF NOT EXIST "%RELEASE%" MKDIR "%RELEASE%"

COPY /Y "%ProjectRoot%\dist\portable\ImageCompressor_Portable.exe" "%RELEASE%\" >NUL 2>&1
COPY /Y "%ProjectRoot%\InstallerOutput\*.exe" "%RELEASE%\" >NUL 2>&1

IF NOT EXIST "%RELEASE%\ImageCompressor_Portable.exe" (
    ECHO    ERROR: Could not copy release files!
    pause & exit /b
)
ECHO    Files ready.
ECHO.

:: Final Cleanup
RMDIR /S /Q "%ProjectRoot%\build" 2>NUL
RMDIR /S /Q "%ProjectRoot%\dist" 2>NUL
RMDIR /S /Q "%ProjectRoot%\InstallerOutput" 2>NUL
IF EXIST "%ProjectRoot%\compressor.spec" DEL /F "%ProjectRoot%\compressor.spec" > NUL 2>&1
IF EXIST "%ProjectRoot%\ImageCompressor_Portable.spec" DEL /F "%ProjectRoot%\ImageCompressor_Portable.spec" > NUL 2>&1
ECHO    Cleanup complete.
ECHO.

ECHO =============================================================
ECHO      BUILD PROCESS COMPLETE!
ECHO =============================================================
ECHO.
ECHO    Your release files are at:
ECHO    %RELEASE%
ECHO.

:: Open the release folder in Explorer
start "" "%RELEASE%"

pause
