# Arranque local de Server Oficina en Windows.
# Mantiene el entorno aislado de la instalación productiva de la Latitude.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Falta .venv. Ejecuta primero .\PREPARAR_LOCAL_WINDOWS.ps1"
}

$env:SERVER_OFICINA_ENV = "development"
$env:SERVER_OFICINA_DATABASE_URL = "sqlite+pysqlite:///./runtime/local/server_oficina.db"
$env:SERVER_OFICINA_DATA_DIR = (Join-Path $PSScriptRoot "runtime\local")
$env:SERVER_OFICINA_SESSION_HOURS = "12"
$env:SERVER_OFICINA_COOKIE_SECURE = "false"
$env:SERVER_OFICINA_HOST = "127.0.0.1"
$env:SERVER_OFICINA_PORT = "8080"

Write-Host "Server Oficina local -> http://127.0.0.1:8080"
Write-Host "CTRL+C detiene el servidor."
Start-Process "http://127.0.0.1:8080"
& $Python run.py
