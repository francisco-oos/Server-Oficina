#!/usr/bin/env bash
set -euo pipefail
exec "$(cd "$(dirname "$0")" && pwd)/scripts/verify-frontend-e2e.sh" "$@"
