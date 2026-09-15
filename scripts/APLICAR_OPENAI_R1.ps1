# Server Oficina · aplicar OpenAI R1 sobre alpha.4
$ErrorActionPreference = "Stop"

$Expected = "0945a438a69ce33b34d532c2b7be7157b88f943b"
$Current = (git rev-parse HEAD).Trim()

if ($Current -ne $Expected) {
    throw "Base incorrecta. HEAD=$Current; se esperaba $Expected"
}
git diff --quiet
if ($LASTEXITCODE -ne 0) {
    throw "El árbol tiene cambios locales. Guárdalos antes de aplicar el relevo."
}

git apply --check OPENAI_ALPHA4_R1.patch
if ($LASTEXITCODE -ne 0) { throw "El patch no aplica limpiamente." }

git apply OPENAI_ALPHA4_R1.patch
Write-Host "OpenAI R1 aplicado. NO haga push todavía: ejecute VALIDAR_SERVER_OFICINA.sh."
