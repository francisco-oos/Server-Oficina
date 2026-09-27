#!/usr/bin/env bash
# Restauración administrativa explícita. Ver docs/operacion/36_BACKUP_RESTORE.md.
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "Uso: sudo $0 /srv/server-oficina/backups/server-oficina/AAAAMMDD-HHMMSS" >&2; exit 1; fi
BACKUP=$(readlink -f "$1")
[[ -d "$BACKUP" ]] || { echo "Backup inexistente: $BACKUP" >&2; exit 2; }
cd "$BACKUP"
sha256sum -c SHA256SUMS
LOCAL_CLOUD=server-oficina-local-cloud
LC_WAS_ACTIVE=$(systemctl is-active "$LOCAL_CLOUD" 2>/dev/null || true)
# El observador se detiene primero: no debe registrar versiones mientras la base
# se reemplaza.
systemctl stop "$LOCAL_CLOUD" 2>/dev/null || true
systemctl stop server-oficina || true
docker exec -i server-oficina-postgres pg_restore -U serveroficina -d server_oficina --clean --if-exists --no-owner < database.dump
if [[ -f app-files.tar.gz ]]; then
  mkdir -p /srv/server-oficina/data/app
  tar -C /srv/server-oficina/data/app -xzf app-files.tar.gz
  chown -R serveroficina:serveroficina /srv/server-oficina/data/app
fi
systemctl start server-oficina
for _ in $(seq 1 20); do curl -fsS http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break; sleep 2; done
curl -fsS http://127.0.0.1:8080/api/health | python3 -m json.tool
if [[ "$LC_WAS_ACTIVE" == active ]]; then systemctl start "$LOCAL_CLOUD"; fi

# Consistencia base ↔ historial (versions/ no viaja en el respaldo diario).
if [[ -x /opt/server-oficina/current/.venv/bin/python && -f /etc/server-oficina/server-oficina.env ]]; then
  /opt/server-oficina/current/scripts/verificar-historial.sh \
    || echo "AVISO: faltan o están dañados objetos de versions/; restaurarlos desde la réplica externa (BACKUP_VERSIONS_DEST) y repetir: sudo ./scripts/verificar-historial.sh --deep" >&2
fi
if [[ -f syncthing-hub-identity.tar.gz ]]; then
  echo "Identidad Syncthing del hub disponible en $BACKUP/syncthing-hub-identity.tar.gz."
  echo "NO se aplica automáticamente: nunca deben operar dos hubs con la misma clave."
  echo "Procedimiento manual: docs/operacion/36_BACKUP_RESTORE.md#identidad-syncthing-del-hub"
fi
