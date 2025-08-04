@echo off
echo Setting up C++ MCP Server virtual environment...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python first.
    echo Download from: https://python.org
    echo.
    pause
    exit /b 1
)

echo Python found. Creating virtual environment...

REM Create virtual environment
python -m venv mcp_env
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    echo.
    pause
    exit /b 1
)

echo Virtual environment created successfully.
echo Activating virtual environment...

REM Activate virtual environment
call mcp_env\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    echo.
    pause
    exit /b 1
)

echo Virtual environment activated.
echo Upgrading pip...

REM Upgrade pip
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip
    echo.
    pause
    exit /b 1
)

echo Installing Python dependencies from requirements.txt...

REM Install dependencies
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install Python packages
    echo.
    pause
    exit /b 1
)

echo.
echo Setting up self-contained libclang...

REM Create lib directory
if not exist "lib\windows" mkdir lib\windows

REM Check if already exists
if exist "lib\windows\libclang.dll" (
    echo ✓ libclang.dll already exists in lib\windows\
    goto :complete
)

echo Downloading libclang.dll directly...

REM Download libclang.dll using separate Python script
python scripts\download_libclang.py
if errorlevel 1 (
    echo Download script failed. Trying fallback options...
)

if exist "lib\windows\libclang.dll" (
    echo ✓ libclang.dll ready for self-contained operation!
) else (
    echo ⚠️  Download failed. Checking for system libclang...
    
    REM Fallback: Try to copy from system LLVM installation
    if exist "C:\Program Files\LLVM\bin\libclang.dll" (
        echo Found system libclang! Copying to lib\windows\...
        copy "C:\Program Files\LLVM\bin\libclang.dll" "lib\windows\" >nul 2>&1
        if not errorlevel 1 echo ✓ Successfully copied libclang.dll
    ) else if exist "C:\Program Files (x86)\LLVM\bin\libclang.dll" (
        echo Found system libclang! Copying to lib\windows\...
        copy "C:\Program Files (x86)\LLVM\bin\libclang.dll" "lib\windows\" >nul 2>&1
        if not errorlevel 1 echo ✓ Successfully copied libclang.dll
    ) else (
        echo.
        echo ❌ Could not get libclang.dll automatically.
        echo Manual setup required:
        echo   1. Go to: https://github.com/llvm/llvm-project/releases/latest
        echo   2. Download: clang+llvm-*-x86_64-pc-windows-msvc.tar.xz
        echo   3. Extract and copy bin/libclang.dll to lib\windows\libclang.dll
    )
)

:complete
echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
if exist "lib\windows\libclang.dll" (
    echo ✓ Self-contained libclang.dll ready
) else (
    echo ⚠️  libclang.dll not found - will try system libraries
)
echo ✓ Virtual environment ready
echo ✓ Python packages installed
echo.
echo Next steps:
echo   1. To test: run_server.bat
echo   2. To manually test: python scripts\test_server.py
echo.
echo If you see any errors above, please review them before continuing.
echo.
pause