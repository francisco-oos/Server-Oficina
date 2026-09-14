#!/usr/bin/env bash
set -euo pipefail
sudo systemctl restart server-oficina
sleep 2
curl -fsS http://127.0.0.1:8080/api/health | python3 -m json.tool
