#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "Uso: sudo $0 /var/lib/server-oficina/backups/AAAAMMDD-HHMMSS"; exit 1; fi
BACKUP="$1"; set -a; source /etc/server-oficina/server-oficina.env; set +a
sha256sum -c "$BACKUP/SHA256SUMS"
systemctl stop server-oficina
PGURL="${SERVER_OFICINA_DATABASE_URL/postgresql+psycopg:\/\//postgresql:\/\/}"
pg_restore --clean --if-exists --no-owner -d "$PGURL" "$BACKUP/database.dump"
tar -C "$SERVER_OFICINA_DATA_DIR" -xzf "$BACKUP/files.tar.gz" || true
chown -R serveroficina:serveroficina "$SERVER_OFICINA_DATA_DIR"
systemctl start server-oficina
curl -fsS http://127.0.0.1:8080/api/health
