@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Server Oficina - Validacion local

cd /d "%~dp0"

echo ============================================================
echo        SERVER OFICINA - VALIDACION LOCAL WINDOWS
echo ============================================================
echo.

set "SERVER_OFICINA_ENV=test"
set "SERVER_OFICINA_DATABASE_URL=sqlite+pysqlite:///./runtime/test/server_oficina_test.db"
set "SERVER_OFICINA_DATA_DIR=./runtime/test"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No existe .venv.
    echo Ejecuta primero INICIAR_SERVER_OFICINA_LOCAL.bat
    pause
    exit /b 1
)

set "PYTHON=.venv\Scripts\python.exe"

echo [1/4] Sintaxis Python...
if exist "scripts\syntax-check.py" (
    "%PYTHON%" scripts\syntax-check.py app tests run.py
) else (
    "%PYTHON%" -m compileall -q app tests run.py
)
if errorlevel 1 goto :fail

echo.
echo [2/4] Suite pytest...
"%PYTHON%" -m pytest -q
if errorlevel 1 goto :fail

echo.
echo [3/4] Contrato frontend...
if exist "scripts\check-frontend-contract.py" (
    "%PYTHON%" scripts\check-frontend-contract.py
    if errorlevel 1 goto :fail
) else (
    echo No existe scripts\check-frontend-contract.py; se omite.
)

echo.
echo [4/4] Sintaxis JavaScript...
where node >nul 2>&1
if errorlevel 1 (
    echo Node.js no esta instalado; se omite esta validacion.
) else (
    if exist "app\static\app.js" (
        node --check app\static\app.js
        if errorlevel 1 goto :fail
    )
    if exist "app\static\admin-management.js" (
        node --check app\static\admin-management.js
        if errorlevel 1 goto :fail
    )
)

echo.
echo ============================================================
echo VALIDACION COMPLETADA SIN ERRORES
echo ============================================================
pause
exit /b 0

:fail
echo.
echo ============================================================
echo VALIDACION FALLIDA
echo Revisa el error mostrado arriba.
echo ============================================================
pause
exit /b 1
