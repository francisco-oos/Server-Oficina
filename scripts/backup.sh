#!/usr/bin/env bash
set -euo pipefail
umask 027
BASE=/srv/server-oficina/backups/server-oficina
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="$BASE/$STAMP"
mkdir -p "$DEST"

docker inspect server-oficina-postgres >/dev/null 2>&1 || { echo "Contenedor PostgreSQL no disponible" >&2; exit 2; }
docker exec server-oficina-postgres pg_dump -U serveroficina -d server_oficina -Fc > "$DEST/database.dump"
if [[ -d /srv/server-oficina/data/app ]]; then
  tar -C /srv/server-oficina/data/app -czf "$DEST/app-files.tar.gz" imports evidence 2>/dev/null || true
fi
cp /opt/server-oficina/current/VERSION "$DEST/VERSION"
(
  cd "$DEST"
  sha256sum database.dump VERSION app-files.tar.gz 2>/dev/null > SHA256SUMS || sha256sum database.dump VERSION > SHA256SUMS
)
chmod 750 "$DEST"
chmod 640 "$DEST"/* 2>/dev/null || true
find "$BASE" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
echo "$DEST"
