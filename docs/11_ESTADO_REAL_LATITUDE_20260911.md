# 11 · Estado real de la Latitude — 2026-09-11

Este documento registra hechos verificados durante la preparación física del host. No sustituye los gates de la aplicación.

## Host

- equipo: Dell Latitude 7220 Rugged Extreme, 8 GiB RAM;
- hostname: `server-oficina`;
- SO: Debian 13 Trixie amd64 con Xfce mínimo;
- SSH activo;
- UFW activo: entrada denegada por defecto y SSH permitido;
- zona horaria: `America/Mexico_City`, NTP sincronizado;
- suspensión, hibernación y hybrid-sleep enmascarados;
- pulsación corta del botón de encendido configurada como `ignore` para evitar apagados accidentales.

## Almacenamiento

- raíz `/`: volumen LVM pequeño para sistema;
- `/var`: volumen pequeño, por lo que **no debe alojar Docker/PostgreSQL de negocio**;
- `/srv`: volumen principal (~86 GiB en el momento de preparación);
- VG interno heredado conserva el nombre `serer-ficina-ADQ-vg`; se mantiene por estabilidad de arranque y no tiene significado funcional.

## Docker

- Docker Engine instalado desde repositorio oficial;
- Docker Root: `/srv/docker/engine`;
- containerd root: `/srv/docker/containerd`;
- Docker Compose plugin operativo;
- prueba `hello-world` aprobada antes y después de reinicio.

## PostgreSQL físico

- imagen: PostgreSQL 18.6;
- contenedor: `server-oficina-postgres`;
- base: `server_oficina`;
- usuario: `serveroficina`;
- persistencia: `/srv/server-oficina/data/postgres:/var/lib/postgresql`;
- health: aprobado;
- persistencia tras reinicio: aprobada;
- `pg_dump` custom: aprobado;
- `pg_restore` a base temporal: aprobado.

## Qué falta validar todavía en host

- instalación de esta alpha.2;
- arranque `systemd` de la aplicación tras reboot;
- bootstrap del primer administrador;
- acceso LAN real desde PC/teléfono;
- importación de copia de Excel real;
- flujo real de baja/rehire;
- permisos RRHH/HSE/Supervisor;
- backup integral de BD + archivos y restore integral;
- navegador E2E real.
