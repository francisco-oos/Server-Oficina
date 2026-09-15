SERVER OFICINA — RELEVO 00

Este paquete NO sustituye el repositorio y NO es una nueva aplicación.
Se aplica encima de Server-Oficina alpha.3.

Objetivo:
- fijar protocolo de relevos;
- permitir preparar, validar y ejecutar la misma base en Windows;
- usar SQLite local aislado antes de desplegar cambios en la Latitude.

Copiar los archivos a la raíz del repositorio respetando la carpeta docs/.

Después:
  Set-ExecutionPolicy -Scope Process Bypass
  .\PREPARAR_LOCAL_WINDOWS.ps1
  .\VALIDAR_LOCAL_WINDOWS.ps1
  .\INICIAR_LOCAL_WINDOWS.ps1
