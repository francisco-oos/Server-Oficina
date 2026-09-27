#!/usr/bin/env bash
set -euo pipefail

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

ROOT=/srv/server-oficina
FILES=$ROOT/files
VERSIONS=$ROOT/versions
SERVICE_USER=serveroficina
SERVICE_GROUP=serveroficina
# Syncthing del hub corre con su propio usuario (miembro del grupo de la app):
# no puede leer /etc/server-oficina ni la BD, pero sí escribir en LAB_SYNC.
SYNC_USER=serveroficina-sync
SYNC_HOME=$ROOT/syncthing

echo "SERVER OFICINA · PRECHECK NUBE LOCAL"
echo "Modo: $([[ $APPLY -eq 1 ]] && echo APLICAR || echo SOLO_LECTURA)"
echo "Hostname: $(hostname)"
df -h "$ROOT" 2>/dev/null || df -h /
free -h || true
echo "Syncthing: $(command -v syncthing || echo NO_INSTALADO)"
command -v syncthing >/dev/null 2>&1 && syncthing --version || true

if [[ $APPLY -ne 1 ]]; then
  echo "No se modificó el sistema."
  echo "Para preparar SOLO el laboratorio: sudo $0 --apply"
  exit 0
fi

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Use sudo para --apply" >&2; exit 1; }
id -u "$SERVICE_USER" >/dev/null 2>&1 || { echo "Falta usuario $SERVICE_USER; instale Server Oficina primero" >&2; exit 2; }

if ! command -v syncthing >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y syncthing
fi
systemctl cat syncthing@.service >/dev/null 2>&1 || { echo "El paquete syncthing no trae syncthing@.service" >&2; exit 3; }

# files/ y versions/ los crea install-tablet.sh; aquí sólo se añade la zona LAB.
# No se crean carpetas de áreas reales ni se cambia recursivamente el dueño de
# files/: los gates destructivos usan sólo archivos sintéticos en LAB_SYNC.
for dir in "$FILES" "$VERSIONS"; do
  [[ -d "$dir" ]] || install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 2770 "$dir"
done
[[ -d "$FILES/LAB_SYNC" ]] || install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 2770 "$FILES/LAB_SYNC"

if ! id -u "$SYNC_USER" >/dev/null 2>&1; then
  useradd --system --gid "$SERVICE_GROUP" --home-dir "$SYNC_HOME" --create-home --shell /usr/sbin/nologin "$SYNC_USER"
fi
chmod 700 "$SYNC_HOME"
runuser -u "$SYNC_USER" -- test -w "$FILES/LAB_SYNC" || { echo "$SYNC_USER no puede escribir en LAB_SYNC" >&2; exit 4; }
systemctl enable --now "syncthing@$SYNC_USER"

# Puertos Syncthing (22000/tcp+udp, 21027/udp) sólo en la LAN confiable; el
# reconciliador los recalcula al cambiar de router/DHCP (scripts/lan_firewall.py).
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q '^Status: active'; then
  python3 "$(cd "$(dirname "$0")" && pwd)/lan_firewall.py" enable syncthing
fi

echo "LAB_PREPARED_OK: $FILES/LAB_SYNC"
echo "Syncthing hub: syncthing@$SYNC_USER (GUI sólo en 127.0.0.1:8384; usar túnel SSH)"
echo "No se configuró ningún peer ni carpeta Syncthing ni Synology: ver runbook."
echo "Siguiente gate: docs/operacion/52_RUNBOOK_GATE_1_PC_LATITUDE.md"
