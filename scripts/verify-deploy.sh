#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for f in scripts/*.sh INICIAR_SERVER_OFICINA.sh DETENER_SERVER_OFICINA.sh REINICIAR_SERVER_OFICINA.sh ESTADO_SERVER_OFICINA.sh LOGS_SERVER_OFICINA.sh VALIDAR_SERVER_OFICINA.sh VALIDAR_BACKEND.sh VALIDAR_FRONTEND.sh VALIDAR_DESPLIEGUE.sh VALIDAR_FRONTEND_E2E.sh BACKUP_SERVER_OFICINA.sh RESTORE_SERVER_OFICINA.sh INSTALAR_EN_TABLETA.sh INSTALAR_ACCESO_ESCRITORIO.sh ABRIR_SERVER_OFICINA.sh GENERAR_MANIFEST.sh; do
  bash -n "$f"
done
python3 - <<'PY'
from pathlib import Path
p=Path('deploy/infra/compose.yml')
s=p.read_text()
for token in ('postgres:18.6','127.0.0.1:5432:5432','/srv/server-oficina/data/postgres:/var/lib/postgresql'):
    assert token in s, token
print('DEPLOY_CONTRACT_OK')
PY
echo "DEPLOY_OK"
