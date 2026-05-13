@echo off
setlocal enabledelayedexpansion
title claw — build EXE

echo.
echo  ================================================
echo   claw — packaging into single EXE
echo  ================================================
echo.

rem ── 1. Build frontend ──────────────────────────────────────────────────────
echo [1/4] Building frontend...
pushd frontend
if not exist node_modules (
    echo       installing npm dependencies...
    call npm install --silent --no-audit --no-fund
    if errorlevel 1 ( echo ERROR: npm install failed & pause & exit /b 1 )
)
call npm run build
if errorlevel 1 ( echo ERROR: vite build failed & pause & exit /b 1 )
popd
echo       frontend/dist ready.

rem ── 2. Set up Python venv ──────────────────────────────────────────────────
echo [2/4] Setting up Python environment...
pushd backend
if not exist .venv (
    python -m venv .venv
    if errorlevel 1 ( echo ERROR: python -m venv failed & pause & exit /b 1 )
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if errorlevel 1 ( echo ERROR: pip install failed & pause & exit /b 1 )
echo       Python environment ready.

rem ── 3. Run PyInstaller ─────────────────────────────────────────────────────
echo [3/4] Running PyInstaller (this takes 1-3 minutes)...
pyinstaller claw.spec --noconfirm --clean
if errorlevel 1 ( echo ERROR: PyInstaller failed & deactivate & popd & pause & exit /b 1 )
deactivate
popd

rem ── 4. Report ──────────────────────────────────────────────────────────────
echo [4/4] Done!
echo.
if exist backend\dist\claw.exe (
    for %%A in (backend\dist\claw.exe) do set SIZE=%%~zA
    set /a SIZE_MB=!SIZE! / 1048576
    echo  Output : backend\dist\claw.exe
    echo  Size   : ~!SIZE_MB! MB
) else (
    echo  ERROR: backend\dist\claw.exe not found — check PyInstaller output above.
    pause
    exit /b 1
)
echo.
echo  Run claw.exe to launch. On first start it will:
echo    * create %%LOCALAPPDATA%%\claw\ with a default .env
echo    * start the backend on http://127.0.0.1:8765
echo    * open your browser automatically
echo    * show a tray icon (right-click to open settings or quit)
echo.
pause
