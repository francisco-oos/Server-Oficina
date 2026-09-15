# Server Oficina se ejecuta en primer plano durante desarrollo.
# El método normal de detención es CTRL+C en la consola donde se inició.
# Este script sólo informa el proceso que ocupa el puerto local para evitar
# terminar procesos ajenos de forma automática.

$ErrorActionPreference = "Stop"

Write-Host "Procesos escuchando en el puerto 8080:"
try {
    Get-NetTCPConnection -LocalPort 8080 -State Listen |
        Select-Object LocalAddress, LocalPort, OwningProcess |
        Format-Table -AutoSize
} catch {
    Write-Host "No se detectó un listener en el puerto 8080."
}
Write-Host "Para desarrollo, detén Server Oficina con CTRL+C en su consola."
