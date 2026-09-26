# 11 · Estado real de la Latitude — 2026-09-11

## Host ya verificado

Dell Latitude 7220 Rugged Extreme, Debian 13/Xfce mínimo, hostname `server-oficina`, SSH y UFW activos, NTP `America/Mexico_City`, suspensión/hibernación bloqueadas y pulsación corta de encendido ignorada.

El VG interno conserva `serer-ficina-ADQ-vg` por estabilidad; no tiene significado funcional.

## Almacenamiento y contenedores

`/var` es pequeño y no aloja datos pesados. `/srv` es el volumen de negocio. Docker Engine usa `/srv/docker/engine` y containerd `/srv/docker/containerd`; ambos fueron comprobados tras reinicio.

PostgreSQL 18.6 corre como `server-oficina-postgres`, persiste en `/srv/server-oficina/data/postgres`, está ligado a loopback para la app y superó persistencia, `pg_dump` y restauración temporal.

## Alpha.2 instalada físicamente

Durante la sesión real se instaló `0.1.0-alpha.2` mediante release versionada, pasó `PACKAGE_OK`, creó `server-oficina.service`/timer de backup, respondió `/api/health`, habilitó acceso LAN 8080 por UFW y permitió crear el primer administrador desde navegador.

También se detectó y documentó el defecto visual `[object Object]` ante validación 422; alpha.3 corrige la serialización de errores y `minlength` en UI.

## Estado de alpha.3

Alpha.3 se construye como actualización aditiva y **no se considera instalada físicamente todavía**. Su instalador hace backup pre-upgrade, conserva la release previa y revierte el symlink `current` si la nueva app no pasa health.
