#!/usr/bin/env bash
# Respaldo verificado de Server Oficina. Ver docs/operacion/36_BACKUP_RESTORE.md.
#
# Qué incluye cada respaldo diario (/srv/server-oficina/backups/server-oficina/<fecha>):
#   database.dump                 pg_dump -Fc (fuente de verdad del estado)
#   app-files.tar.gz              imports/ y evidence/ de data/app
#   versions-inventory.tsv        objetos del ContentStore (sha256 \t bytes)
#   syncthing-hub-identity.tar.gz cert/key/config del Syncthing del hub (0600; SECRETO)
#   BACKUP_INFO, SHA256SUMS
#
# versions/ NO se copia dentro del respaldo diario (sería duplicar GB cada día en
# el mismo disco). Su réplica va a un destino EXTERNO opcional configurado en
# /etc/server-oficina/backup.env (BACKUP_VERSIONS_DEST=...). Sin él, el respaldo
# lo declara explícitamente: la historia depende de un único disco.
set -euo pipefail
umask 027
DATA=/srv/server-oficina
BASE=$DATA/backups/server-oficina
VERSIONS=$DATA/versions
SYNC_HOME=${SYNC_HUB_HOME:-$DATA/syncthing}
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="$BASE/$STAMP"
# shellcheck disable=SC1091
[[ -f /etc/server-oficina/backup.env ]] && source /etc/server-oficina/backup.env
mkdir -p "$BASE"
# Dos respaldos en el mismo segundo (manual + timer) nunca comparten directorio.
if [[ -e "$DEST" ]]; then DEST=$(mktemp -d "$BASE/$STAMP-XXXX"); else mkdir "$DEST"; fi

docker inspect server-oficina-postgres >/dev/null 2>&1 || { echo "Contenedor PostgreSQL no disponible" >&2; exit 2; }
docker exec server-oficina-postgres pg_dump -U serveroficina -d server_oficina -Fc > "$DEST/database.dump"

APP_DIRS=()
for dir in imports evidence; do [[ -d "$DATA/data/app/$dir" ]] && APP_DIRS+=("$dir"); done
if (( ${#APP_DIRS[@]} )); then
  tar -C "$DATA/data/app" -czf "$DEST/app-files.tar.gz" "${APP_DIRS[@]}"
fi
cp /opt/server-oficina/current/VERSION "$DEST/VERSION"
[[ -f /opt/server-oficina/current/RELEASE_INFO ]] && cp /opt/server-oficina/current/RELEASE_INFO "$DEST/RELEASE_INFO"

OBJECTS=0; BYTES=0
if [[ -d "$VERSIONS/sha256" ]]; then
  find "$VERSIONS/sha256" -type f ! -name '.*' -printf '%f\t%s\n' | LC_ALL=C sort > "$DEST/versions-inventory.tsv"
  OBJECTS=$(wc -l < "$DEST/versions-inventory.tsv")
  BYTES=$(awk -F'\t' '{s+=$2} END {print s+0}' "$DEST/versions-inventory.tsv")
fi

IDENTITY=NO_ENCONTRADA
KEY=$(find "$SYNC_HOME" -maxdepth 5 -name key.pem -type f 2>/dev/null | head -1 || true)
if [[ -n "$KEY" ]]; then
  CONF_DIR=$(dirname "$KEY")
  ( umask 077; tar -C "$CONF_DIR" -czf "$DEST/syncthing-hub-identity.tar.gz" cert.pem key.pem config.xml )
  chmod 600 "$DEST/syncthing-hub-identity.tar.gz"
  IDENTITY="$CONF_DIR"
fi

REPLICA=NO_CONFIGURADA
if [[ -n "${BACKUP_VERSIONS_DEST:-}" ]]; then
  # Fail closed: si el destino externo no está montado no se escribe en el disco
  # local fingiendo ser una réplica.
  if [[ "${BACKUP_REQUIRE_MOUNT:-1}" == 1 ]] && ! mountpoint -q "$(dirname "$BACKUP_VERSIONS_DEST")" && ! mountpoint -q "$BACKUP_VERSIONS_DEST"; then
    echo "BACKUP_VERSIONS_FAIL: $BACKUP_VERSIONS_DEST no está montado" >&2
    REPLICA=FALLO_NO_MONTADO
  else
    mkdir -p "$BACKUP_VERSIONS_DEST"
    NEW=$(rsync -a --ignore-existing --out-format='%n' "$VERSIONS/sha256/" "$BACKUP_VERSIONS_DEST/sha256/" | grep -v '/$' || true)
    BAD=0
    while IFS= read -r rel; do
      [[ -z "$rel" ]] && continue
      [[ "$(sha256sum "$BACKUP_VERSIONS_DEST/sha256/$rel" | cut -d' ' -f1)" == "$(basename "$rel")" ]] || BAD=$((BAD+1))
    done <<< "$NEW"
    if (( BAD )); then REPLICA="FALLO_VERIFICACION:$BAD"; else REPLICA="OK:$(grep -c . <<< "$NEW" || true)_nuevos"; fi
  fi
fi

cat > "$DEST/BACKUP_INFO" <<INFO
fecha=$STAMP
release=$(readlink -f /opt/server-oficina/current)
versions_objetos=$OBJECTS
versions_bytes=$BYTES
versions_replica_externa=$REPLICA
syncthing_hub_identidad=$IDENTITY
INFO
( cd "$DEST" && find . -maxdepth 1 -type f ! -name SHA256SUMS -printf '%f\n' | LC_ALL=C sort | xargs sha256sum > SHA256SUMS )
chmod 750 "$DEST"
chmod 640 "$DEST"/* 2>/dev/null || true
[[ -f "$DEST/syncthing-hub-identity.tar.gz" ]] && chmod 600 "$DEST/syncthing-hub-identity.tar.gz"
# Retención: sólo respaldos diarios. Los pre-upgrade-* son puntos de rollback de
# la base y no se borran automáticamente.
find "$BASE" -mindepth 1 -maxdepth 1 -type d -name '[0-9]*' -mtime +30 -exec rm -rf {} +
[[ "$REPLICA" == NO_CONFIGURADA ]] && echo "AVISO: versions/ sin réplica externa (BACKUP_VERSIONS_DEST)" >&2
[[ "$REPLICA" == FALLO* ]] && { echo "$DEST"; exit 3; }
echo "$DEST"
