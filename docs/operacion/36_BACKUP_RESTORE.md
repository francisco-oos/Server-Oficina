# 36 · Respaldo y restauración

## Qué hay que respaldar

| Qué | Dónde | Cómo |
|---|---|---|
| Base de datos | PostgreSQL en Docker | `pg_dump -Fc` |
| Archivos de la aplicación | `/srv/server-oficina/data/app` | copia del árbol |
| Credenciales SMB | `/etc/server-oficina` | **root-only, fuera del respaldo ordinario** |
| Evidencias en NAS | repositorio SMB | lo respalda el NAS; Server Oficina sólo indexa |

La base es la fuente de verdad del estado; los archivos de `data/app` guardan
los originales de importación y las evidencias del repositorio LOCAL.

## Respaldo

```bash
./BACKUP_SERVER_OFICINA.sh
```

Produce un `pg_dump -Fc` con su hash. Hay además un `systemd` timer
(`server-oficina-backup.timer`) para ejecutarlo periódicamente.

Antes de promover una release, el instalador hace un respaldo **pre-upgrade** de
forma automática. Si `/api/health` falla tras promover, revierte el symlink
`current` a la release anterior.

## Restauración

```bash
./RESTORE_SERVER_OFICINA.sh <archivo-de-respaldo>
```

La restauración es **una acción administrativa explícita, nunca automática**.
Un restore no anunciado sobre un sistema en uso destruiría el trabajo capturado
desde el último respaldo.

Procedimiento recomendado:

1. Detener el servicio (`./DETENER_SERVER_OFICINA.sh`).
2. Restaurar primero a una **base temporal** y verificar que carga.
3. Restaurar a la base real.
4. Restaurar `data/app` si el corte lo requiere.
5. Arrancar y comprobar `GET /api/health` y el inicio de sesión.

## Qué NO se respalda

- **Credenciales SMB.** Viven en `/etc/server-oficina` con permisos 600 y
  fuera de PostgreSQL a propósito. Se reponen con
  `./CONFIGURAR_NAS_EVIDENCIAS.sh`.
- **Archivos que viven en el NAS.** Server Oficina los indexa sin moverlos; su
  respaldo es responsabilidad del NAS. Tras restaurar, los `EvidenceRecord`
  apuntarán a rutas del repositorio: si el NAS se perdió, los registros
  quedarán íntegros pero sin archivo, lo cual es visible y auditable.

## Verificación periódica recomendada

Un respaldo que nunca se ha restaurado no es un respaldo. Conviene restaurar a
una base temporal de forma regular y confirmar que la aplicación arranca contra
ella. `pg_dump -Fc` + `pg_restore` a base temporal ya se validó físicamente en
la Latitude para la línea base alpha.2.
