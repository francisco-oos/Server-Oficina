#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python3
[[ -x .venv/bin/python ]] && PY=.venv/bin/python
"$PY" -m compileall -q app tests run.py
"$PY" -m pytest -q
echo "BACKEND_OK"
