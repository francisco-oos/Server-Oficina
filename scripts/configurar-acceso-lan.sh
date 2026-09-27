#!/usr/bin/env bash
# Publicación LAN de Server Oficina, fail-closed y multi-LAN.
#
# La Latitude puede estar a la vez en una LAN por Ethernet y en otra por Wi-Fi.
# Server Oficina sólo escucha en 0.0.0.0 si TODO esto se demuestra:
#   1. UFW activo con política entrante por defecto deny/reject;
#   2. al menos una LAN activa es confiable (identidad por LAN: MAC del gateway
#      + perfil de NetworkManager + SSID; ver scripts/lan_firewall.py);
#   3. las reglas gestionadas (sólo la subred RFC1918 de cada LAN confiable,
#      sólo en su interfaz) quedaron aplicadas y verificadas;
#   4. la API responde /api/health tras el cambio.
# Después, server-oficina-lan-firewall mantiene el invariante: si no queda
# ninguna LAN confiable (o UFW deja de proteger) vuelve a 127.0.0.1, y vuelve a
# 0.0.0.0 cuando regresa alguna. La Latitude nunca enruta entre sus LAN.
# Si algo falla: SERVER_OFICINA_HOST=127.0.0.1, "LAN_NO_PUBLICADA: <causa>" y
# salida 10. Nunca desactiva UFW ni abre 8080 a cualquier origen, y nunca toca
# reglas ajenas (SSH).
#
#   sudo ./scripts/configurar-acceso-lan.sh                           publicar las LAN ya confiables
#   sudo ./scripts/configurar-acceso-lan.sh --confiar-red-actual      confiar en LA red actual (sólo si hay una)
#   sudo ./scripts/configurar-acceso-lan.sh --confiar-interfaz enp0s31f6 --confiar-interfaz wlp2s0
#                                                                     confiar en la LAN de cada interfaz nombrada
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "Ejecute con sudo/root" >&2; exit 1; fi
SRC=$(cd "$(dirname "$0")/.." && pwd)
ENV_FILE=/etc/server-oficina/server-oficina.env
FW=("python3" "$SRC/scripts/lan_firewall.py")
usage() { echo "Uso: $0 [--confiar-red-actual] [--confiar-interfaz IF]..." >&2; exit 2; }
TRUST=0
TRUST_IFACES=()
while (($#)); do
  case "$1" in
    --confiar-red-actual) TRUST=1 ;;
    --confiar-interfaz) [[ $# -ge 2 && -n "$2" ]] || usage; TRUST_IFACES+=(--interface "$2"); shift ;;
    *) usage ;;
  esac
  shift
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
  # El reconciliador deja de publicar hasta que esta publicación se repita con éxito.
  "${FW[@]}" api off >/dev/null 2>&1 || true
  [[ -f "$ENV_FILE" ]] && { set_host 127.0.0.1 || true; }
  echo "LAN_NO_PUBLICADA: $1" >&2
  echo "Server Oficina queda sólo en 127.0.0.1 (no expuesto en ninguna LAN)." >&2
  echo "Tras verificar qué LAN son de la oficina: sudo $0 --confiar-interfaz <if> [--confiar-interfaz <if>]" >&2
  exit 10
}
# Cualquier error inesperado deja la API sólo en loopback.
trap '[[ $PUBLISHED == 1 ]] || local_only "error inesperado en la configuración LAN"' EXIT

# Un solo actor a la vez: el reconciliador (timer/dispatcher) espera a que esto termine.
exec 8>/run/server-oficina-lan-firewall.lock
flock -w 120 8 || local_only "el reconciliador LAN no liberó el bloqueo"
export SO_LAN_FIREWALL_LOCK_HELD=1

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

if (( ${#TRUST_IFACES[@]} )); then
  "${FW[@]}" trust-current "${TRUST_IFACES[@]}" || local_only "no se pudo identificar o confiar la LAN indicada"
elif [[ $TRUST == 1 ]]; then
  "${FW[@]}" trust-current \
    || local_only "no se pudo confiar la red actual (¿varias LAN activas? use --confiar-interfaz <if>)"
fi
"${FW[@]}" apply --require-rules \
  || local_only "ninguna LAN activa es confiable o las reglas no quedaron verificadas"

"${FW[@]}" api on >/dev/null
set_host 0.0.0.0
if systemctl is-active --quiet server-oficina && ! wait_health; then
  local_only "la API no respondió tras publicarla en la LAN"
fi
PUBLISHED=1
echo "LAN_PUBLICADA: 8080 sólo desde la subred RFC1918 de cada LAN confiable activa, por su interfaz:"
"${FW[@]}" status | sed -n 's/^LAN_FIREWALL //p' | python3 -c '
import json, sys
report = json.load(sys.stdin)
for n in report["networks"]:
    ip = (n["address"] or "").split("/")[0]
    if n["status"] == "confiable":
        print("  %s (%s): http://%s:8080  LAN %s" % (n["iface"], n["medium"], ip, n["subnet"]))
    else:
        print("  %s (%s): NO publicada (%s)" % (n["iface"], n["medium"], n["status"]))
' || true
echo "  Nombre local (mDNS/Avahi, en cada LAN con la IP de esa LAN): http://server-oficina.local:8080"
