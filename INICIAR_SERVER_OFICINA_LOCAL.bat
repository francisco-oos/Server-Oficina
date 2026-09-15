@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Server Oficina - Modo local

cd /d "%~dp0"

echo ============================================================
echo        SERVER OFICINA - ENTORNO LOCAL WINDOWS
echo ============================================================
echo.

REM ------------------------------------------------------------
REM Configuracion local aislada
REM ------------------------------------------------------------
set "SERVER_OFICINA_ENV=development"
set "SERVER_OFICINA_DATABASE_URL=sqlite+pysqlite:///./runtime/local/server_oficina.db"
set "SERVER_OFICINA_DATA_DIR=./runtime/local"
set "SERVER_OFICINA_HOST=127.0.0.1"
set "SERVER_OFICINA_PORT=8080"

if not exist "runtime\local" mkdir "runtime\local"

REM ------------------------------------------------------------
REM Localizar Python
REM ------------------------------------------------------------
where py >nul 2>&1
if %errorlevel%==0 (
    set "PY_LAUNCHER=py -3.12"
    py -3.12 --version >nul 2>&1
    if errorlevel 1 set "PY_LAUNCHER=py"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se encontro Python.
        echo Instala Python 3.12 o superior y vuelve a ejecutar este archivo.
        echo.
        pause
        exit /b 1
    )
    set "PY_LAUNCHER=python"
)

REM ------------------------------------------------------------
REM Crear entorno virtual si no existe
REM ------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creando entorno virtual...
    %PY_LAUNCHER% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear .venv
        pause
        exit /b 1
    )
) else (
    echo [1/4] Entorno virtual encontrado.
)

set "PYTHON=.venv\Scripts\python.exe"

REM ------------------------------------------------------------
REM Instalar dependencias solo la primera vez
REM ------------------------------------------------------------
if not exist ".venv\.server_oficina_preparado" (
    echo [2/4] Preparando dependencias...
    "%PYTHON%" -m pip install --upgrade pip
    if errorlevel 1 goto :pip_error

    if exist "requirements-dev.txt" (
        "%PYTHON%" -m pip install -r requirements-dev.txt
    ) else if exist "requirements.txt" (
        "%PYTHON%" -m pip install -r requirements.txt
    ) else (
        echo [ERROR] No se encontro requirements-dev.txt ni requirements.txt
        pause
        exit /b 1
    )

    if errorlevel 1 goto :pip_error
    type nul > ".venv\.server_oficina_preparado"
    echo Dependencias preparadas.
) else (
    echo [2/4] Dependencias ya preparadas.
)

REM ------------------------------------------------------------
REM Comprobar que existe el punto de entrada
REM ------------------------------------------------------------
if not exist "run.py" (
    echo [ERROR] No se encontro run.py en:
    echo %CD%
    echo.
    echo Coloca este .BAT en la raiz del repositorio Server-Oficina.
    pause
    exit /b 1
)

echo [3/4] Base local:
echo       runtime\local\server_oficina.db
echo.

echo [4/4] Iniciando Server Oficina...
echo       http://127.0.0.1:8080
echo.
echo Para detener el servidor presiona CTRL+C.
echo ============================================================
echo.

REM Abrir navegador despues de un pequeno margen.
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8080"

"%PYTHON%" run.py

echo.
echo Server Oficina se detuvo.
pause
exit /b 0

:pip_error
echo.
echo [ERROR] Fallo la instalacion de dependencias.
echo Revisa el mensaje anterior.
pause
exit /b 1
