#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "Uso: sudo $0 /srv/server-oficina/backups/server-oficina/AAAAMMDD-HHMMSS" >&2; exit 1; fi
BACKUP=$(readlink -f "$1")
[[ -d "$BACKUP" ]] || { echo "Backup inexistente: $BACKUP" >&2; exit 2; }
cd "$BACKUP"
sha256sum -c SHA256SUMS
systemctl stop server-oficina || true
docker exec -i server-oficina-postgres pg_restore -U serveroficina -d server_oficina --clean --if-exists --no-owner < database.dump
if [[ -f app-files.tar.gz ]]; then
  mkdir -p /srv/server-oficina/data/app
  tar -C /srv/server-oficina/data/app -xzf app-files.tar.gz
  chown -R serveroficina:serveroficina /srv/server-oficina/data/app
fi
systemctl start server-oficina
sleep 3
curl -fsS http://127.0.0.1:8080/api/health | python3 -m json.tool
