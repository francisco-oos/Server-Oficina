#!/usr/bin/env bash
set -euo pipefail
exec sudo "$(cd "$(dirname "$0")" && pwd)/scripts/install-desktop-launchers.sh" "$@"
