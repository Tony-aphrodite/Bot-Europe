@echo off
chcp 65001 > nul
title EU Registry Bot - Complete Build

echo ================================================
echo   EU Registry Bot - Complete Build (All-in-One)
echo ================================================
echo.

:: Check Python
echo [1/5] Verificando Python...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python no instalado.
    pause
    exit /b 1
)
echo       Python OK

:: Check Node.js
echo [2/5] Verificando Node.js...
node --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js no instalado.
    pause
    exit /b 1
)
echo       Node.js OK

:: Install Python dependencies
echo [3/5] Instalando dependencias Python...
pip install -r requirements.txt pyinstaller > nul 2>&1
echo       Dependencias Python OK

:: Build Python API as executable
echo [4/5] Construyendo API Server (.exe)...
pyinstaller --onefile --name api_server --distpath . --workpath build_temp --specpath build_temp ^
    --hidden-import flask ^
    --hidden-import flask_cors ^
    --hidden-import selenium ^
    --hidden-import webdriver_manager ^
    --hidden-import cryptography ^
    --hidden-import apscheduler ^
    --hidden-import yaml ^
    --hidden-import pydantic ^
    --hidden-import colorlog ^
    --add-data "config;config" ^
    --add-data "src;src" ^
    api/server.py

if %errorlevel% neq 0 (
    echo ERROR: Fallo la construccion del API server.
    pause
    exit /b 1
)
echo       API Server OK

:: Build Electron app
echo [5/5] Construyendo Electron App...
cd desktop
call npm install > nul 2>&1
call npm run build:win

if %errorlevel% neq 0 (
    echo ERROR: Fallo la construccion de Electron.
    cd ..
    pause
    exit /b 1
)
cd ..

:: Copy API server to build folder
echo.
echo Copiando archivos...
copy api_server.exe desktop\build\win-unpacked\ > nul 2>&1
xcopy /E /I /Y config desktop\build\win-unpacked\config > nul 2>&1
xcopy /E /I /Y data desktop\build\win-unpacked\data > nul 2>&1
mkdir desktop\build\win-unpacked\certificates > nul 2>&1
mkdir desktop\build\win-unpacked\logs > nul 2>&1

:: Cleanup
echo Limpiando archivos temporales...
rmdir /S /Q build_temp > nul 2>&1
del api_server.exe > nul 2>&1

echo.
echo ================================================
echo   BUILD COMPLETADO!
echo ================================================
echo.
echo La aplicacion esta lista en:
echo   desktop\build\win-unpacked\
echo.
echo Archivos incluidos:
echo   - EU Registry Bot.exe (Aplicacion principal)
echo   - api_server.exe (Servidor API integrado)
echo   - config\ (Configuraciones)
echo   - data\ (Datos)
echo   - certificates\ (Coloca tu certificado aqui)
echo.
echo Para distribuir: Copia toda la carpeta "win-unpacked"
echo.
pause
