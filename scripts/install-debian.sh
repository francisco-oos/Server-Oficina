#!/usr/bin/env bash
set -euo pipefail
echo "install-debian.sh fue reemplazado en alpha.2 por install-tablet.sh (Docker PostgreSQL + /srv)." >&2
exec "$(cd "$(dirname "$0")" && pwd)/install-tablet.sh" "$@"
