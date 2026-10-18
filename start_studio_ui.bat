@echo off
title AI Music & Video MCP Studio - Web UI Dashboard
echo =====================================================================
echo           AI Music ^& Video MCP Studio - Launcher
echo =====================================================================
echo.
cd /d "%~dp0\web-ui"

echo [1/3] Checking Node.js environment...
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Node.js is not found in PATH!
    pause
    exit /b 1
)

echo [2/3] Starting Next.js Studio Server on http://localhost:3000 ...
start "" http://localhost:3000
npm run dev

pause
