#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-http://127.0.0.1:8080}
curl -fsS "$BASE/api/health" | python3 -m json.tool
curl -fsS "$BASE/api/setup/status" | python3 -m json.tool
curl -fsS -o /dev/null "$BASE/"
curl -fsS -o /dev/null "$BASE/static/app.js"
curl -fsS -o /dev/null "$BASE/static/styles.css"
echo "SMOKE_OK"
