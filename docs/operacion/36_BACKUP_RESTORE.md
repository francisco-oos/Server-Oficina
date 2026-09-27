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

Acción administrativa explícita. Garantía: **nunca queda una base a medias
anunciada como restaurada**. El restore anterior ejecutaba
`pg_restore --clean` directamente sobre `server_oficina`; con un dump truncado
dejaba tablas vaciadas, API y observador detenidos y ningún mensaje de fallo
(reproducido en `tests/integration/restore_lab.py` con PostgreSQL real).

| Fase | Qué hace | Si falla |
|---|---|---|
| 1 · Validación | `SHA256SUMS` estricto (`database.dump` y `app-files.tar.gz` deben figurar); lectura **completa** del dump (`pg_restore -f /dev/null`, sin escribir en ninguna base); `tar -tzf` completo y sólo rutas bajo `imports/` y `evidence/`; la base `server_oficina` existe | salida **20**: nada se tocó, servicios intactos |
| 2 · Preparación | base **nueva** `server_oficina_restore_<fecha>` (`TEMPLATE template0`) con `pg_restore --single-transaction --exit-on-error --no-owner`: o entra entero o no entra nada; archivos en `data/app/.restore-staging-<fecha>` | salida **21**: se descartan la base temporal y el staging (creados por esta ejecución); base viva, `data/app` y servicios **nunca** se detuvieron |
| 3 · Intercambio | detiene observador y API; **un único COMMIT** renombra `server_oficina` → `server_oficina_pre_restore_<fecha>` y la preparada → `server_oficina`; `imports/` y `evidence/` vivos se **mueven** a `data/app/.pre-restore-<fecha>/` y los preparados ocupan su lugar | vuelta atrás (fase 4) |
| 4 · Health | arranca la API y espera `/api/health`; rearranca el observador si estaba activo | salida **22**: se deshace el intercambio (base y archivos previos, servicios como estaban). Si la vuelta atrás no se completa, o la API tampoco responde con los datos previos: salida **23** `RESTORE_FAIL_CRITICO`, servicios **detenidos a propósito** |

Resultado:

* `RESTORE_OK` (salida 0) sólo tras `/api/health` con los datos restaurados.
  Salida 24 (`RESTORE_AVISO`): datos restaurados y API sana, pero el observador
  no volvió a arrancar.
* Cada ejecución deja `/srv/server-oficina/backups/restore-logs/restore-<fecha>.txt`
  (`resultado`, `codigo`, `detalle`, `fase`, base previa, archivos previos,
  estado de los servicios). La ruta se imprime al final.
* Un error inesperado (`set -e`) se trata según la fase: nunca termina en
  silencio.

Qué **no** se borra:

* La base previa queda como `server_oficina_pre_restore_<fecha>`. Borrarla a
  mano tras verificar (`docker exec server-oficina-postgres psql -U serveroficina
  -d postgres -c 'DROP DATABASE server_oficina_pre_restore_<fecha>'`).
  Mientras tanto ocupa espacio: el restore necesita sitio para dos copias.
* `imports/` y `evidence/` previos quedan íntegros en
  `data/app/.pre-restore-<fecha>/` (root, 0700), con
  `DIFERENCIAS_CON_RESPALDO.tsv`: archivos `ausente_en_respaldo` (subidos
  después del respaldo) y `distinto_en_respaldo` (modificados). Revisar antes de
  borrar; lo que haya que conservar se vuelve a importar por la aplicación.
* Sólo se eliminan la base temporal y el staging creados por la propia
  ejecución (nombre único con fecha), y sólo cuando se descartan.

Otros directorios de `data/app` (p. ej. `backups/`) no forman parte del
respaldo y no se tocan. Un dump con permisos (`GRANT`) a roles que no existen
en el servidor falla en la fase 2 (salida 21) sin tocar nada: crear el rol y
repetir.

Después del restore el script ejecuta `verificar-historial.sh`. Si informa
faltantes de `versions/`:

1. copiar desde la réplica externa
   `rsync -a --ignore-existing <BACKUP_VERSIONS_DEST>/sha256/ /srv/server-oficina/versions/sha256/`;
2. repetir `sudo ./scripts/verificar-historial.sh --deep` hasta `HISTORY_OK`.

Comprobar además inicio de sesión y `GET /api/local-cloud/shares` (estado del
observador).

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

Un respaldo que nunca se ha restaurado no es un respaldo. Restaurar con
regularidad (el propio restore prepara en una base temporal) y ejecutar
`verificar-historial.sh --deep`. En la Latitude se validó `pg_dump`/`pg_restore`
para la línea base alpha.2; este restore transaccional está probado **sólo en
laboratorio** (`tests/integration/restore_lab.py`, PostgreSQL 16 de la
distribución); en la Latitude (PostgreSQL 18.6 en Docker), con `versions/` e
identidad del hub, es **gate físico pendiente (NOT RUN)**.
