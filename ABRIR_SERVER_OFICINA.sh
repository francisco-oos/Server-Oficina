#!/usr/bin/env bash
set -euo pipefail
URL=${1:-http://127.0.0.1:8080}
if command -v xdg-open >/dev/null 2>&1; then exec xdg-open "$URL"; fi
echo "$URL"
