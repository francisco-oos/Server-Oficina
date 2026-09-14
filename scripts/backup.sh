#!/usr/bin/env bash
set -euo pipefail
set -a; source /etc/server-oficina/server-oficina.env; set +a
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="${SERVER_OFICINA_DATA_DIR}/backups/${STAMP}"
mkdir -p "$DEST"
PGURL="${SERVER_OFICINA_DATABASE_URL/postgresql+psycopg:\/\//postgresql:\/\/}"
pg_dump "$PGURL" -Fc -f "$DEST/database.dump"
tar -C "$SERVER_OFICINA_DATA_DIR" -czf "$DEST/files.tar.gz" imports evidence 2>/dev/null || true
sha256sum "$DEST"/* > "$DEST/SHA256SUMS"
find "${SERVER_OFICINA_DATA_DIR}/backups" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
echo "$DEST"
