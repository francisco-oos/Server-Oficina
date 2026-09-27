# 36 · Respaldo y restauración

Actualizado 2026-09-27 para la Fase 1 (historial `versions/` e identidad del hub).

## Qué hay que respaldar para restaurar Server Oficina **y** la continuidad del hub

| Qué | Dónde | Cómo | En Git |
|---|---|---|---|
| Base de datos | PostgreSQL en Docker | `pg_dump -Fc` diario + `pre-upgrade-*` en cada instalación | no |
| Archivos de la aplicación | `/srv/server-oficina/data/app` (`imports/`, `evidence/`) | `app-files.tar.gz` | no |
| Historial de contenido | `/srv/server-oficina/versions` (objetos `sha256/xx/<hash>`) | inventario diario + **réplica externa** opcional verificada | no |
| Identidad Syncthing del hub | `cert.pem`, `key.pem`, `config.xml` del usuario `serveroficina-sync` | `syncthing-hub-identity.tar.gz` (0600) | **nunca** |
| Archivos de trabajo sincronizados | `/srv/server-oficina/files` | los tienen además las PCs; el historial los cubre desde que se observaron | no |
| Configuración | `/etc/server-oficina/*.env`, `lan-firewall.json` | la regenera el instalador; las claves añadidas por el operador se anotan aparte | no |
| Credenciales SMB | `/etc/server-oficina/smb-*` | root-only, fuera del respaldo ordinario; se reponen con `CONFIGURAR_NAS_EVIDENCIAS.sh` | no |

`key.pem` es la identidad criptográfica del hub: quien la tenga puede
suplantarlo ante las PCs. El respaldo local es `0600` root; **cualquier copia
fuera del host debe ir cifrada** y jamás a Git, a PostgreSQL ni a un chat.

## Respaldo

```bash
sudo ./BACKUP_SERVER_OFICINA.sh          # también server-oficina-backup.timer, diario 03:15
```

Cada respaldo (`/srv/server-oficina/backups/server-oficina/<fecha>/`) contiene
`database.dump`, `app-files.tar.gz`, `versions-inventory.tsv`,
`syncthing-hub-identity.tar.gz` (si existe), `VERSION`, `RELEASE_INFO`,
`BACKUP_INFO` y `SHA256SUMS` (rutas relativas: verificable fuera del host).

`BACKUP_INFO` declara `versions_replica_externa`:

* `NO_CONFIGURADA`: la historia depende de un único disco (aviso en el journal).
* `OK:<n>_nuevos`: réplica al día; cada objeto nuevo se verificó por SHA-256.
* `FALLO_NO_MONTADO` / `FALLO_VERIFICACION:<n>`: el respaldo sale con código 3
  (el timer queda en fallo visible).

### Réplica externa de `versions/`

`versions/` no se copia dentro del respaldo diario (duplicaría GB cada día en el
mismo disco). Se replica de forma incremental a un disco externo o NAS montado:

```bash
# /etc/server-oficina/backup.env   (root, 0600)
BACKUP_VERSIONS_DEST=/mnt/respaldo/server-oficina-versions
# BACKUP_REQUIRE_MOUNT=1   (por defecto) exige que el destino o su padre sea un punto de montaje
```

Si el destino no está montado **no** se escribe en el disco local fingiendo ser
una réplica (fail-closed). Los objetos son inmutables: `rsync --ignore-existing`
nunca reescribe uno existente.

### Retención

Se conservan 30 días de respaldos diarios. Los `pre-upgrade-*` (puntos de
retorno de la base por instalación) **no** se borran automáticamente.

## Restauración

```bash
sudo ./RESTORE_SERVER_OFICINA.sh /srv/server-oficina/backups/server-oficina/<fecha>
```

Acción administrativa explícita. El script verifica `SHA256SUMS`, detiene el
observador y la API, restaura base y `data/app`, espera el health, rearranca el
observador si estaba activo y ejecuta `python -m app.workers.verify_history`.

Procedimiento recomendado:

1. Detener el servicio y restaurar primero a una **base temporal**.
2. Restaurar la base real con el script.
3. Si `verify_history` informa faltantes: copiar desde la réplica externa
   `rsync -a --ignore-existing <BACKUP_VERSIONS_DEST>/sha256/ /srv/server-oficina/versions/sha256/`
   y repetir `python -m app.workers.verify_history --deep` hasta `HISTORY_OK`.
4. Comprobar `GET /api/health`, inicio de sesión y `GET /api/local-cloud/shares`
   (estado del observador).

### Identidad Syncthing del hub

No se aplica automáticamente: **nunca deben operar dos hubs con la misma
clave**. Sólo para reemplazar el hub (disco nuevo, equipo nuevo) con el anterior
apagado:

```bash
sudo systemctl stop syncthing@serveroficina-sync
CONF=$(sudo find /srv/server-oficina/syncthing -maxdepth 5 -name config.xml -printf '%h\n' | head -1)
sudo tar -C "$CONF" -xzf <respaldo>/syncthing-hub-identity.tar.gz
sudo chown serveroficina-sync:serveroficina "$CONF"/{cert.pem,key.pem,config.xml}
sudo chmod 600 "$CONF/key.pem"
sudo systemctl start syncthing@serveroficina-sync
```

Las PCs vuelven a ver el mismo Device ID sin reconfigurarse. Sin este archivo,
el hub nuevo tiene otra identidad y cada PC debe aceptarlo de nuevo.

## Qué NO se respalda

- **Credenciales SMB** (ver tabla).
- **Archivos que viven en el NAS**: los respalda el NAS; Server Oficina sólo los
  indexa y los registros quedan íntegros aunque el archivo falte.
- **Base de datos interna de Syncthing**: se reconstruye reescaneando.

## Verificación periódica

Un respaldo que nunca se ha restaurado no es un respaldo. Restaurar a una base
temporal con regularidad y ejecutar `verify_history --deep`. En la Latitude se
validó `pg_dump`/`pg_restore` para la línea base alpha.2; la restauración con
`versions/` e identidad del hub es **gate físico pendiente**.
