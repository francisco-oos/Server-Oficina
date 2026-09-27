#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/verify-backend.sh
./scripts/verify-frontend.sh
./scripts/verify-deploy.sh
# Detecta hash distinto, archivo faltante y archivo no listado en el manifiesto.
./scripts/generate-manifest.sh --check
echo "PACKAGE_OK"
