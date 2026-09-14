#!/usr/bin/env bash
set -u
INFRA=/srv/server-oficina/app/infra/compose.yml
echo "=== SERVER OFICINA ==="
systemctl --no-pager --full status server-oficina | sed -n '1,18p'
echo
echo "=== POSTGRESQL ==="
if [[ -f "$INFRA" ]]; then sudo docker compose -f "$INFRA" ps; else echo "No existe $INFRA"; fi
echo
echo "=== HEALTH ==="
curl -fsS http://127.0.0.1:8080/api/health 2>/dev/null | python3 -m json.tool || echo "Health no disponible"
echo
echo "=== ALMACENAMIENTO ==="
df -h / /var /srv
echo
echo "=== RED ==="
ip -br -4 a
