#!/usr/bin/env bash
set -euo pipefail

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

ROOT=/srv/server-oficina
FILES=$ROOT/files
VERSIONS=$ROOT/versions
SERVICE_USER=serveroficina
SERVICE_GROUP=serveroficina

echo "SERVER OFICINA · PRECHECK NUBE LOCAL"
echo "Modo: $([[ $APPLY -eq 1 ]] && echo APLICAR || echo SOLO_LECTURA)"
echo "Hostname: $(hostname)"
df -h "$ROOT" 2>/dev/null || df -h /
free -h || true
echo "Syncthing: $(command -v syncthing || echo NO_INSTALADO)"

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

mkdir -p "$FILES"/{RRHH,Seguridad,Transporte,Control_Material,LAB} "$VERSIONS"
chown -R "$SERVICE_USER":"$SERVICE_GROUP" "$FILES" "$VERSIONS"
chmod 2770 "$FILES" "$VERSIONS" "$FILES"/*

if [[ -f /opt/server-oficina/current/deploy/server-oficina-local-cloud.service ]]; then
  install -m 0644 /opt/server-oficina/current/deploy/server-oficina-local-cloud.service /etc/systemd/system/server-oficina-local-cloud.service
  systemctl daemon-reload
fi

echo "LAB_PREPARED_OK"
echo "No se habilitó ningún peer, observador ni Synology."
echo "Siguiente gate: docs/42_PLAN_PRUEBAS_NUBE_LOCAL_24_CLIENTES.md"
