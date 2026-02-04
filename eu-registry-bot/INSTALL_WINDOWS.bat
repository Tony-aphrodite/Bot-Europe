@echo off
chcp 65001 > nul
title EU Registry Bot - Instalador

echo ========================================
echo   EU Registry Bot - Instalador Windows
echo ========================================
echo.

:: Check Python
echo [1/4] Verificando Python...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python no esta instalado.
    echo Por favor, descarga Python de: https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)
echo       Python OK

:: Check Node.js
echo [2/4] Verificando Node.js...
node --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js no esta instalado.
    echo Por favor, descarga Node.js de: https://nodejs.org/
    pause
    exit /b 1
)
echo       Node.js OK

:: Install Python dependencies
echo [3/4] Instalando dependencias Python...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Fallo la instalacion de dependencias Python.
    pause
    exit /b 1
)
echo       Dependencias Python OK

:: Install Node.js dependencies and build
echo [4/4] Instalando dependencias y construyendo aplicacion...
cd desktop
call npm install
if %errorlevel% neq 0 (
    echo ERROR: Fallo la instalacion de dependencias Node.js.
    pause
    exit /b 1
)

call npm run build:win
if %errorlevel% neq 0 (
    echo ERROR: Fallo la construccion de la aplicacion.
    pause
    exit /b 1
)

cd ..

echo.
echo ========================================
echo   INSTALACION COMPLETADA!
echo ========================================
echo.
echo El instalador se encuentra en:
echo   desktop\build\EU Registry Bot Setup.exe
echo.
echo Copia tu certificado (.p12 o .pfx) a la carpeta:
echo   certificates\
echo.
pause
