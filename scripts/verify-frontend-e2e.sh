#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
BROWSER=${SERVER_OFICINA_E2E_BROWSER:-}
if [[ -z "$BROWSER" ]]; then
  for c in /usr/bin/chromium /usr/bin/chromium-browser /usr/bin/google-chrome /usr/bin/google-chrome-stable; do
    if [[ -x "$c" ]]; then BROWSER="$c"; break; fi
  done
fi
[[ -n "$BROWSER" ]] || { echo "E2E_BLOCKED: no se encontró Chromium/Chrome" >&2; exit 3; }
# Algunos entornos administrados bloquean toda navegación por política global.
if grep -RqsE '"URLBlocklist"[[:space:]]*:[[:space:]]*\[[[:space:]]*"\*"' /etc/chromium/policies/managed /etc/opt/chrome/policies/managed 2>/dev/null; then
  echo "E2E_BLOCKED: Chromium tiene una política administrada URLBlocklist=*; ejecute este gate en la Latitude/QA host" >&2
  exit 3
fi
python3 -c 'import playwright' >/dev/null 2>&1 || { echo "E2E_BLOCKED: instale requirements-e2e.txt" >&2; exit 3; }
TMP=$(mktemp -d /tmp/server-oficina-e2e.XXXXXX)
PORT=${SERVER_OFICINA_E2E_PORT:-18081}
export SERVER_OFICINA_DATABASE_URL="sqlite+pysqlite:///$TMP/e2e.db"
export SERVER_OFICINA_DATA_DIR="$TMP/data"
export SERVER_OFICINA_HOST=127.0.0.1
export SERVER_OFICINA_PORT="$PORT"
export SERVER_OFICINA_E2E_URL="http://127.0.0.1:$PORT"
export SERVER_OFICINA_E2E_BROWSER="$BROWSER"
python3 run.py >"$TMP/server.log" 2>&1 &
PID=$!
cleanup(){ kill "$PID" >/dev/null 2>&1 || true; wait "$PID" >/dev/null 2>&1 || true; rm -rf "$TMP"; }
trap cleanup EXIT
for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then break; fi
  sleep 0.25
done
curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null || { cat "$TMP/server.log" >&2; exit 4; }
python3 tests/e2e/ui_smoke.py
