#!/usr/bin/env bash
# Publicación LAN de Server Oficina, fail-closed.
#
# Server Oficina sólo escucha en 0.0.0.0 si TODO esto se demuestra:
#   1. UFW activo con política entrante por defecto deny/reject;
#   2. la red actual es confiable (identidad: MAC del gateway + perfil de
#      NetworkManager + SSID; ver scripts/lan_firewall.py);
#   3. las reglas gestionadas (sólo subred RFC1918 actual, sólo esa interfaz)
#      quedaron aplicadas y verificadas;
#   4. la API responde /api/health tras el cambio.
# Si algo falla: SERVER_OFICINA_HOST=127.0.0.1, API reiniciada si hacía falta,
# "LAN_NO_PUBLICADA: <causa>" y salida 10. Nunca desactiva UFW ni abre 8080 a
# cualquier origen, y nunca toca reglas ajenas (SSH).
#
#   sudo ./scripts/configurar-acceso-lan.sh                       publicar si la red ya es confiable
#   sudo ./scripts/configurar-acceso-lan.sh --confiar-red-actual  confiar en esta red (decisión explícita) y publicar
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "Ejecute con sudo/root" >&2; exit 1; fi
SRC=$(cd "$(dirname "$0")/.." && pwd)
ENV_FILE=/etc/server-oficina/server-oficina.env
TRUST=0
for arg in "$@"; do
  case "$arg" in
    --confiar-red-actual) TRUST=1 ;;
    *) echo "Uso: $0 [--confiar-red-actual]" >&2; exit 2 ;;
  esac
done
PUBLISHED=0

current_host() { sed -n 's/^SERVER_OFICINA_HOST=//p' "$ENV_FILE" | tail -1; }

set_host() {  # set_host HOST: reescribe el env y reinicia la API si cambió
  [[ "$(current_host)" == "$1" ]] && return 0
  if grep -q '^SERVER_OFICINA_HOST=' "$ENV_FILE"; then
    sed -i "s/^SERVER_OFICINA_HOST=.*/SERVER_OFICINA_HOST=$1/" "$ENV_FILE"
  else
    echo "SERVER_OFICINA_HOST=$1" >> "$ENV_FILE"
  fi
  if systemctl is-active --quiet server-oficina; then systemctl restart server-oficina; fi
}

wait_health() {
  for _ in $(seq 1 20); do
    curl -fsS http://127.0.0.1:8080/api/health >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

local_only() {
  trap - EXIT
  set_host 127.0.0.1 || true
  echo "LAN_NO_PUBLICADA: $1" >&2
  echo "Server Oficina queda sólo en 127.0.0.1 (no expuesto en la LAN)." >&2
  echo "Tras verificar que ésta es la red de la oficina: sudo $0 --confiar-red-actual" >&2
  exit 10
}
# Cualquier error inesperado deja la API sólo en loopback.
trap '[[ $PUBLISHED == 1 ]] || local_only "error inesperado en la configuración LAN"' EXIT

[[ -f "$ENV_FILE" ]] || local_only "no existe $ENV_FILE (instalar primero)"
command -v ufw >/dev/null 2>&1 || local_only "UFW no está instalado"
ufw status | grep -q '^Status: active' || local_only "UFW no está activo"
ufw status verbose | grep -Eq '^Default: (deny|reject) \(incoming\)' \
  || local_only "la política entrante por defecto de UFW no es deny/reject"

install -m 0644 "$SRC/deploy/lan-firewall/server-oficina-lan-firewall.service" /etc/systemd/system/server-oficina-lan-firewall.service
install -m 0644 "$SRC/deploy/lan-firewall/server-oficina-lan-firewall.timer" /etc/systemd/system/server-oficina-lan-firewall.timer
if [[ -d /etc/NetworkManager/dispatcher.d ]]; then
  install -m 0755 "$SRC/deploy/lan-firewall/90-server-oficina-lan" /etc/NetworkManager/dispatcher.d/90-server-oficina-lan
fi
systemctl daemon-reload
systemctl enable --now server-oficina-lan-firewall.timer

if [[ $TRUST == 1 ]]; then
  python3 "$SRC/scripts/lan_firewall.py" trust-current || local_only "no se pudo identificar o confiar la red actual"
fi
python3 "$SRC/scripts/lan_firewall.py" apply --require-rules \
  || local_only "la red actual no es confiable o las reglas no quedaron verificadas"

set_host 0.0.0.0
if systemctl is-active --quiet server-oficina && ! wait_health; then
  local_only "la API no respondió tras publicarla en la LAN"
fi
PUBLISHED=1
echo "LAN_PUBLICADA: 8080 sólo desde la subred RFC1918 de la red confiable actual"
