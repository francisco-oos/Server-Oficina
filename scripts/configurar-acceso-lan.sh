#!/usr/bin/env bash
# Acceso LAN a Server Oficina que sobrevive a cambios de router/SSID/DHCP.
#
# Antes se fijaba en UFW la subred vigente al instalar; al cambiar de red había
# que reconfigurar a mano. Ahora la confianza es por red (SSID o cable) y la
# subred se recalcula en cada cambio: ver scripts/lan_firewall.py.
#
#   sudo ./scripts/configurar-acceso-lan.sh            instala y confía en la red actual si no hay ninguna
#   sudo ./scripts/lan_firewall.py trust-current       confiar en la red actual (decisión explícita)
#   sudo ./scripts/lan_firewall.py status              qué reglas corresponden ahora y por qué
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "Ejecute con sudo/root" >&2; exit 1; fi
SRC=$(cd "$(dirname "$0")/.." && pwd)
if ! command -v ufw >/dev/null 2>&1 || ! ufw status | grep -q '^Status: active'; then
  echo "UFW no está activo. No se modificó firewall." >&2
  exit 0
fi
install -m 0644 "$SRC/deploy/lan-firewall/server-oficina-lan-firewall.service" /etc/systemd/system/server-oficina-lan-firewall.service
install -m 0644 "$SRC/deploy/lan-firewall/server-oficina-lan-firewall.timer" /etc/systemd/system/server-oficina-lan-firewall.timer
if [[ -d /etc/NetworkManager/dispatcher.d ]]; then
  install -m 0755 "$SRC/deploy/lan-firewall/90-server-oficina-lan" /etc/NetworkManager/dispatcher.d/90-server-oficina-lan
  echo "Dispatcher NetworkManager instalado"
else
  echo "Sin NetworkManager: sólo el timer de respaldo (cada 2 min) reconcilia UFW"
fi
systemctl daemon-reload
python3 "$SRC/scripts/lan_firewall.py" apply --trust-current-if-empty
systemctl enable --now server-oficina-lan-firewall.timer
