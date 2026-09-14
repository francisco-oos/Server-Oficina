#!/usr/bin/env bash
set -euo pipefail
INFRA=/srv/server-oficina/app/infra/compose.yml
if [[ ! -f "$INFRA" ]]; then echo "Falta $INFRA. Ejecute primero INSTALAR_EN_TABLETA.sh" >&2; exit 2; fi
sudo docker compose -f "$INFRA" up -d postgres
sudo systemctl start server-oficina
sleep 2
curl -fsS http://127.0.0.1:8080/api/health | python3 -m json.tool
