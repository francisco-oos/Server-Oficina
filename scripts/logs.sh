#!/usr/bin/env bash
set -euo pipefail
sudo journalctl -u server-oficina -u server-oficina-local-cloud -f --no-pager
