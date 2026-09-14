#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "Ejecute con sudo/root" >&2; exit 1; fi
TARGET_USER=${SUDO_USER:-$USER}
HOME_DIR=$(getent passwd "$TARGET_USER" | cut -d: -f6)
DESKTOP="$HOME_DIR/Desktop"
[[ -d "$HOME_DIR/Escritorio" ]] && DESKTOP="$HOME_DIR/Escritorio"
mkdir -p "$DESKTOP"
install -m 0755 "$(dirname "$0")/../deploy/desktop/Server Oficina.desktop" "$DESKTOP/Server Oficina.desktop"
chown "$TARGET_USER":"$TARGET_USER" "$DESKTOP/Server Oficina.desktop" 2>/dev/null || true
echo "Acceso instalado en: $DESKTOP/Server Oficina.desktop"
