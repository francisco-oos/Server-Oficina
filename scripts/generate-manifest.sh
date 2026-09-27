#!/usr/bin/env bash
# Genera MANIFEST.sha256 con el contenido publicable de la release.
#
# Se excluye todo lo que no forma parte del artefacto entregado: el repositorio
# git, el entorno virtual, los datos de ejecución, la caché, secretos locales
# (.env) y la ficha RELEASE_INFO que escribe el instalador. Incluir `.git`
# haría que el manifiesto dejara de verificar en cuanto git escribiera cualquier
# cosa, y además publicaría el historial dentro del paquete.
#
# Uso:
#   generate-manifest.sh           reescribe MANIFEST.sha256
#   generate-manifest.sh --check   falla si el árbol no coincide exactamente:
#                                  hash distinto, archivo faltante o archivo
#                                  no listado (sha256sum -c no detecta este último)
set -euo pipefail
cd "$(dirname "$0")/.."
MODE=${1:-write}
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
find . -type f \
  ! -path './.git/*' \
  ! -path './.venv/*' \
  ! -path './venv/*' \
  ! -name '.gitattributes' \
  ! -path './.env' \
  ! -path './RELEASE_INFO' \
  ! -path './runtime/*' \
  ! -path './tests/runtime/*' \
  ! -path './.pytest_cache/*' \
  ! -path './reports/.*' \
  ! -path '*/__pycache__/*' \
  ! -name '*.pyc' \
  ! -name 'test.db' \
  ! -name 'MANIFEST.sha256' \
  -print0 | LC_ALL=C sort -z | while IFS= read -r -d '' f; do
    sha256sum "${f#./}"
  done > "$TMP"

if [[ "$MODE" == "--check" ]]; then
  if [[ ! -f MANIFEST.sha256 ]]; then
    echo "MANIFEST_FAIL: falta MANIFEST.sha256" >&2
    exit 1
  fi
  if ! diff -u MANIFEST.sha256 "$TMP" > "$TMP.diff"; then
    echo "MANIFEST_FAIL: el árbol no coincide con MANIFEST.sha256 (regenerar con ./GENERAR_MANIFEST.sh)" >&2
    head -n 60 "$TMP.diff" >&2
    rm -f "$TMP.diff"
    exit 1
  fi
  rm -f "$TMP.diff"
  echo "MANIFEST_CHECK_OK $(wc -l < MANIFEST.sha256) archivos"
  exit 0
fi

mv "$TMP" MANIFEST.sha256
trap - EXIT
echo "MANIFEST_OK $(wc -l < MANIFEST.sha256) archivos"
