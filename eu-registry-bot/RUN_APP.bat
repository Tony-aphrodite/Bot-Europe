@echo off
chcp 65001 > nul
title EU Registry Bot

echo Iniciando EU Registry Bot...
echo.

:: Start API server in background
start /b python api\server.py

:: Wait for API to start
timeout /t 3 /nobreak > nul

:: Start Electron app
cd desktop
call npm start

:: When app closes, kill Python process
taskkill /f /im python.exe > nul 2>&1
