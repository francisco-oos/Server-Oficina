#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "Ejecute con sudo/root" >&2; exit 1; fi
IFACE=${1:-$(ip -4 route show default | awk 'NR==1{print $5}')}
[[ -n "$IFACE" ]] || { echo "No se detectó interfaz por defecto" >&2; exit 2; }
SUBNET=$(ip -4 route show dev "$IFACE" scope link | awk '$1 ~ /^[0-9].*\// {print $1; exit}')
[[ -n "$SUBNET" ]] || { echo "No se detectó subred IPv4 de $IFACE" >&2; exit 3; }
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q '^Status: active'; then
  ufw allow in on "$IFACE" from "$SUBNET" to any port 8080 proto tcp comment 'Server Oficina LAN'
  echo "Acceso HTTP permitido sólo desde $SUBNET por $IFACE hacia 8080/tcp"
else
  echo "UFW no está activo. No se modificó firewall." >&2
fi
