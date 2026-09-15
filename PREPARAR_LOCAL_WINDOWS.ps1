# Server Oficina - preparación reproducible para desarrollo local en Windows.
# No modifica Docker, PostgreSQL ni la instalación de la Latitude.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Assert-Command($Name, $Message) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw $Message
    }
}

Assert-Command "python" "No se encontró Python en PATH. Instala Python 3.12+ y vuelve a ejecutar."
Write-Host "[1/5] Python:" (python --version)

if (-not (Test-Path ".venv")) {
    Write-Host "[2/5] Creando entorno virtual .venv..."
    python -m venv .venv
} else {
    Write-Host "[2/5] .venv ya existe."
}

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "El entorno virtual no contiene el ejecutable esperado: $Python"
}

Write-Host "[3/5] Actualizando pip..."
& $Python -m pip install --upgrade pip

Write-Host "[4/5] Instalando dependencias de desarrollo..."
& $Python -m pip install -r requirements-dev.txt

Write-Host "[5/5] Creando directorio runtime local..."
New-Item -ItemType Directory -Force -Path "runtime\local" | Out-Null

Write-Host ""
Write-Host "Entorno local preparado correctamente."
Write-Host "Siguiente paso: .\VALIDAR_LOCAL_WINDOWS.ps1"
