@echo off
echo ============================================
echo   Stopping Web3 News Scraper Services
echo ============================================
echo.

echo [1/3] Stopping Backend (FastAPI)...
REM Kill Python/FastAPI processes
taskkill /FI "WINDOWTITLE eq News Scraper Backend*" /F >nul 2>&1
taskkill /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *fastapi*" /F >nul 2>&1

echo [2/3] Stopping Frontend (pnpm/Vite)...
REM Kill pnpm/Vite processes
taskkill /FI "WINDOWTITLE eq News Scraper Frontend*" /F >nul 2>&1
taskkill /FI "IMAGENAME eq node.exe" /FI "WINDOWTITLE eq *vite*" /F >nul 2>&1
taskkill /FI "IMAGENAME eq pnpm.exe" /F >nul 2>&1

echo [3/3] Cleaning up...
timeout /t 1 /nobreak >nul

echo.
echo ============================================
echo   All services stopped successfully!
echo ============================================
echo.
pause
