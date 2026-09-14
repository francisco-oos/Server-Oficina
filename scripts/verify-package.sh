#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/verify-backend.sh
./scripts/verify-frontend.sh
./scripts/verify-deploy.sh
if [[ -f MANIFEST.sha256 ]]; then
  sha256sum -c MANIFEST.sha256
fi
echo "PACKAGE_OK"
