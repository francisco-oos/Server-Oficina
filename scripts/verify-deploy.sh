#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for f in scripts/*.sh INICIAR_SERVER_OFICINA.sh DETENER_SERVER_OFICINA.sh REINICIAR_SERVER_OFICINA.sh ESTADO_SERVER_OFICINA.sh LOGS_SERVER_OFICINA.sh VALIDAR_SERVER_OFICINA.sh VALIDAR_BACKEND.sh VALIDAR_FRONTEND.sh VALIDAR_DESPLIEGUE.sh VALIDAR_FRONTEND_E2E.sh BACKUP_SERVER_OFICINA.sh RESTORE_SERVER_OFICINA.sh INSTALAR_EN_TABLETA.sh INSTALAR_ACCESO_ESCRITORIO.sh ABRIR_SERVER_OFICINA.sh GENERAR_MANIFEST.sh CONFIGURAR_NAS_EVIDENCIAS.sh CONFIGURAR_BANDEJA_EVIDENCIAS.sh; do
  bash -n "$f"
done
python3 - <<'PY'
from pathlib import Path
p=Path('deploy/infra/compose.yml')
s=p.read_text()
for token in ('postgres:18.6','127.0.0.1:5432:5432','/srv/server-oficina/data/postgres:/var/lib/postgresql'):
    assert token in s, token
installer=Path('scripts/install-tablet.sh').read_text()
for token in ('PRE_UPGRADE_BACKUP_OK','ROLLBACK_RELEASE_OK','pg_dump','readlink -f "$CURRENT"',
              'assert_new_release','LOCAL_CLOUD=server-oficina-local-cloud','LOCAL_CLOUD_OK',
              'SERVER_OFICINA_SYNC_ROOT=','SERVER_OFICINA_VERSIONS_ROOT='):
    assert token in installer, token
assert 'releases/$VERSION' not in installer, 'la release no puede nombrarse sólo por VERSION'
nas=Path('scripts/configurar-repositorio-smb.sh').read_text()
assert '/etc/server-oficina/smb-' in nas and 'chmod 600' in nas
print('DEPLOY_CONTRACT_OK')
PY
echo "DEPLOY_OK"
