@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Server Oficina - Reiniciar datos locales

cd /d "%~dp0"

echo ============================================================
echo       SERVER OFICINA - BORRAR DATOS LOCALES DE PRUEBA
echo ============================================================
echo.
echo Esta accion SOLO elimina runtime\local.
echo No toca Git, codigo, .venv, PostgreSQL ni la Latitude.
echo.
choice /C SN /M "Deseas continuar"
if errorlevel 2 exit /b 0

if exist "runtime\local" (
    rmdir /S /Q "runtime\local"
)

mkdir "runtime\local" >nul 2>&1

echo.
echo Datos locales eliminados.
echo La proxima ejecucion iniciara con una base SQLite nueva.
pause
