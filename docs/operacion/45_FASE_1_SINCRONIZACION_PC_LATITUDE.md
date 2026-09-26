# 45 · Fase 1 — Sincronización PCs ↔ Latitude

## Objetivo

Antes de introducir LLMs por área, Server Oficina debe demostrar que puede mantener una carpeta de oficina local-first entre varias computadoras Windows y la Dell Latitude 7220 sin depender de Internet ni del Synology.

## Alcance

PCs de oficina ⇄ LAN ⇄ Latitude + SSD.

Synology queda fuera del primer gate. Se conectará después de demostrar que el hub local funciona y que una caída del NAS no afecta a las PCs.

## Criterios de aceptación

1. crear un archivo en una PC y verlo en Latitude y otra PC autorizada;
2. modificarlo y conservar versión/procedencia;
3. desconectar una PC, modificar y reconciliar al volver;
4. no perder dos ediciones concurrentes;
5. conservar conflictos en vez de elegir un ganador silencioso;
6. ignorar temporales de Office;
7. no propagar un borrado destructivo sin política de Server Oficina;
8. conocer progreso y pendientes por carpeta;
9. trabajar sin Internet;
10. recuperar el estado después de reiniciar Latitude o una PC.

## Motor y topología

Syncthing se usa como transporte. Server Oficina mantiene identidad, versiones, auditoría, leases y reglas de conflicto.

La configuración propuesta es estrella y LAN-only: descubrimiento local habilitado; descubrimiento global, relays y NAT traversal deshabilitados; PCs sin auto-accept ni introducer; carpetas send/receive; versionado Staggered como segunda red de seguridad.

## Trabajo simultáneo

Cuando ambas PCs tienen conexión con la Latitude, los leases coordinan un único escritor. Si una PC trabaja offline, no se promete exclusión: se preservan ambas versiones y se reconcilian al regresar. Nunca se hace merge binario ciego de XLSX.

## Orden de pruebas físicas

1. una PC Windows + Latitude, carpeta LAB;
2. dos PCs;
3. cinco PCs;
4. ensayo de 20+ clientes;
5. sólo entonces carpetas reales por área.

Durante esta fase no se conecta ningún LLM ni se usan documentos reales de oficina. Primero se aísla y cierra la sincronización.