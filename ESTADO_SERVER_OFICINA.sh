#!/usr/bin/env bash
set -u
exec "$(cd "$(dirname "$0")" && pwd)/scripts/status.sh" "$@"
