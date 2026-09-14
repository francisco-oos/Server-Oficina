#!/usr/bin/env bash
set -euo pipefail
sudo systemctl stop server-oficina
# PostgreSQL se deja activo por defecto para evitar apagar la fuente de verdad accidentalmente.
echo "Server Oficina detenido. PostgreSQL permanece activo."
