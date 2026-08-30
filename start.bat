@echo off
setlocal enabledelayedexpansion
title Web3 News Scraper - Startup
color 0B

REM ============================================
REM   Web3 News Scraper - Smart Startup
REM ============================================

echo.
echo ================================================
echo    WEB3 NEWS SCRAPER - SMART STARTUP v2.0
echo ================================================
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Check if Poetry is installed
echo [CHECK] Verifying Poetry installation...
where poetry >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Poetry is not installed!
    echo [INFO]  Please install Poetry: https://python-poetry.org/docs/#installation
    echo.
    pause
    exit /b 1
)
echo [OK] Poetry is installed

REM Check if Node/pnpm is installed
echo [CHECK] Verifying pnpm installation...
where pnpm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pnpm is not installed!
    echo [INFO]  Please install pnpm: npm install -g pnpm
    echo.
    pause
    exit /b 1
)
echo [OK] pnpm is installed
echo.

REM Check if backend dependencies are installed
echo [CHECK] Checking backend dependencies...
if not exist "news-scraper-backend\poetry.lock" (
    echo [WARN] Backend dependencies not found
    echo [INFO] Installing backend dependencies...
    cd news-scraper-backend
    call poetry install
    cd ..
    echo [OK] Backend dependencies installed
) else (
    echo [OK] Backend dependencies found
)

REM Check if frontend dependencies are installed
echo [CHECK] Checking frontend dependencies...
if not exist "news-scraper-frontend\node_modules" (
    echo [WARN] Frontend dependencies not found
    echo [INFO] Installing frontend dependencies with pnpm...
    cd news-scraper-frontend
    call pnpm install
    cd ..
    echo [OK] Frontend dependencies installed
) else (
    echo [OK] Frontend dependencies found
)

echo.
echo ================================================
echo    STARTING SERVICES
echo ================================================
echo.

echo [START] Backend Server (FastAPI)...
echo         URL: http://localhost:8000
echo         Docs: http://localhost:8000/docs
start "News Scraper Backend" cmd /k "title News Scraper Backend && color 0A && cd /d "%SCRIPT_DIR%news-scraper-backend" && echo [BACKEND] Starting FastAPI server... && poetry run fastapi dev app/main.py"

echo [WAIT] Waiting for backend to initialize (5 seconds)...
timeout /t 5 /nobreak >nul

echo [START] Frontend Server (Vite)...
echo         URL: http://localhost:5173
start "News Scraper Frontend" cmd /k "title News Scraper Frontend && color 0E && cd /d "%SCRIPT_DIR%news-scraper-frontend" && echo [FRONTEND] Starting Vite dev server... && pnpm dev --host"

echo.
echo ================================================
echo    SERVICES STARTED SUCCESSFULLY!
echo ================================================
echo.
echo Services are running in separate windows:
echo.
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:5173
echo  API Docs: http://localhost:8000/docs
echo.
echo ------------------------------------------------
echo  Quick Actions:
echo ------------------------------------------------
echo  1. Open Frontend:  start http://localhost:5173
echo  2. Open API Docs:  start http://localhost:8000/docs
echo  3. Trigger Scrape: curl -X POST http://localhost:8000/scrape
echo  4. View Articles:  curl http://localhost:8000/articles
echo.
echo ------------------------------------------------
echo  To stop all services:
echo ------------------------------------------------
echo  - Close the Backend and Frontend windows, OR
echo  - Run stop-all.bat
echo.
echo ================================================

REM Ask if user wants to open browser
echo.
choice /C YN /M "Do you want to open the frontend in your browser"
if errorlevel 2 goto :skip_browser
if errorlevel 1 (
    echo [INFO] Opening browser...
    timeout /t 2 /nobreak >nul
    start http://localhost:5173
)

:skip_browser
echo.
echo Press any key to exit this startup window...
echo (Services will continue running in background windows)
pause >nul
