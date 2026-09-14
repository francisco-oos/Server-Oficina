#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m compileall -q app tests run.py
node --check app/static/app.js
bash -n scripts/install-debian.sh scripts/backup.sh scripts/restore.sh scripts/smoke.sh
pytest
