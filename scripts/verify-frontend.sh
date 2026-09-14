#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v node >/dev/null 2>&1 || { echo "Node requerido sólo para validación sintáctica de app.js" >&2; exit 2; }
node --check app/static/app.js
python3 scripts/check-frontend-contract.py
echo "FRONTEND_OK"
