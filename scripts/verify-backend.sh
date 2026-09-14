#!/usr/bin/env bash
# Gate de backend. Debe poder ejecutarse tanto en el árbol de desarrollo como
# sobre una release instalada en modo sólo lectura (/opt/server-oficina/current):
# por eso no se compila a __pycache__ ni se escribe caché de pytest en el árbol.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python3
[[ -x .venv/bin/python ]] && PY=.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1
"$PY" scripts/syntax-check.py app tests run.py
"$PY" -m pytest -q
echo "BACKEND_OK"
