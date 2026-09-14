#!/usr/bin/env bash
# Genera MANIFEST.sha256 con el contenido publicable de la release.
#
# Se excluye todo lo que no forma parte del artefacto entregado: el repositorio
# git, el entorno virtual, los datos de ejecución y la caché. Incluir `.git`
# haría que el manifiesto dejara de verificar en cuanto git escribiera cualquier
# cosa, y además publicaría el historial dentro del paquete.
set -euo pipefail
cd "$(dirname "$0")/.."
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
find . -type f \
  ! -path './.git/*' \
  ! -path './.venv/*' \
  ! -path './venv/*' \
  ! -name '.gitattributes' \
  ! -path './runtime/*' \
  ! -path './tests/runtime/*' \
  ! -path './.pytest_cache/*' \
  ! -path './reports/.*' \
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
