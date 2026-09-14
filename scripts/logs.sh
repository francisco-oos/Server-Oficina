#!/usr/bin/env bash
set -euo pipefail
sudo journalctl -u server-oficina -f --no-pager
