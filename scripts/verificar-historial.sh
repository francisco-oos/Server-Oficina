#!/usr/bin/env bash
# Consistencia base ↔ versions/ con el entorno de producción, como serveroficina.
#   sudo ./scripts/verificar-historial.sh            existencia + tamaño
#   sudo ./scripts/verificar-historial.sh --deep     además recalcula SHA-256
# Imprime HISTORY_OK / HISTORY_FAIL. Nunca modifica nada.
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "Ejecute con sudo/root" >&2; exit 1; fi
exec runuser -u serveroficina -- bash -c '
  set -a; . /etc/server-oficina/server-oficina.env; set +a
  cd /opt/server-oficina/current
  exec .venv/bin/python -m app.workers.verify_history "$@"' _ "$@"
