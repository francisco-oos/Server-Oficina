# Server Oficina - gate PRE/POST para Windows.
# Usa una base SQLite aislada y nunca la base PostgreSQL de producción.

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

Write-Host "=== Server Oficina / Validación local ==="
Write-Host "Base: SQLite aislada"
Write-Host "Datos:" $env:SERVER_OFICINA_DATA_DIR

Write-Host "`n[1/3] compileall"
& $Python -m compileall -q app tests run.py
if ($LASTEXITCODE -ne 0) { throw "compileall falló" }

Write-Host "`n[2/3] pytest"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "pytest falló" }

Write-Host "`n[3/3] sintaxis frontend"
if (Get-Command node -ErrorAction SilentlyContinue) {
    node --check app/static/app.js
    if ($LASTEXITCODE -ne 0) { throw "node --check falló" }
} else {
    Write-Warning "Node.js no está disponible. Se omite node --check; no se marca como PASS."
}

Write-Host "`nVALIDACION_LOCAL_OK"
