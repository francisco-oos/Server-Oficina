#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
find . -type f \
  ! -path './.venv/*' \
  ! -path './runtime/*' \
  ! -path './.pytest_cache/*' \
  ! -path '*/__pycache__/*' \
  ! -name '*.pyc' \
  ! -name 'test.db' \
  ! -name 'MANIFEST.sha256' \
  -print0 | sort -z | while IFS= read -r -d '' f; do
    sha256sum "${f#./}"
  done > "$TMP"
mv "$TMP" MANIFEST.sha256
trap - EXIT
echo "MANIFEST_OK $(wc -l < MANIFEST.sha256) archivos"
