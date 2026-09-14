#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "Ejecute con sudo/root" >&2; exit 1; fi
SRC=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(cat "$SRC/VERSION")
RELEASE=/opt/server-oficina/releases/$VERSION
CURRENT=/opt/server-oficina/current
CONF=/etc/server-oficina
DATA=/srv/server-oficina
INFRA=$DATA/app/infra
SERVICE_USER=serveroficina
SERVICE_GROUP=serveroficina
STAMP=$(date +%Y%m%d-%H%M%S)
PREVIOUS=$(readlink -f "$CURRENT" 2>/dev/null || true)

command -v docker >/dev/null 2>&1 || { echo "Docker no está instalado" >&2; exit 2; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose plugin no está disponible" >&2; exit 3; }

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip rsync curl openssl nodejs
getent group "$SERVICE_GROUP" >/dev/null || groupadd --system "$SERVICE_GROUP"
id -u "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --gid "$SERVICE_GROUP" --home /nonexistent --shell /usr/sbin/nologin "$SERVICE_USER"
mkdir -p /opt/server-oficina/releases "$CONF" "$DATA"/{app/infra,data/app,data/postgres,backups,secrets}
if [[ ! -s "$DATA/secrets/postgres_password" ]]; then
  openssl rand -hex 32 > "$DATA/secrets/postgres_password"
  chmod 600 "$DATA/secrets/postgres_password"
fi

# Copiar y validar la nueva release ANTES de tocar el puntero current.
rsync -a --delete --exclude '.venv' --exclude '__pycache__' --exclude 'runtime' --exclude 'tests/test.db' --exclude 'tests/runtime' "$SRC/" "$RELEASE/"
python3 -m venv "$RELEASE/.venv"
"$RELEASE/.venv/bin/pip" install --upgrade pip
"$RELEASE/.venv/bin/pip" install -r "$RELEASE/requirements-dev.txt"
( cd "$RELEASE" && ./scripts/verify-package.sh )

# Backup pre-upgrade real y verificable. La actualización alpha.3 sólo añade
# tablas, pero el dump permite volver atrás ante cualquier comportamiento no
# esperado en producción.
if docker inspect server-oficina-postgres >/dev/null 2>&1; then
  PREBACK="$DATA/backups/server-oficina/pre-upgrade-${VERSION}-${STAMP}"
  mkdir -p "$PREBACK"
  if docker exec server-oficina-postgres pg_isready -U serveroficina -d server_oficina >/dev/null 2>&1; then
    docker exec server-oficina-postgres pg_dump -U serveroficina -d server_oficina -Fc > "$PREBACK/database.dump"
    if [[ -n "$PREVIOUS" && -f "$PREVIOUS/VERSION" ]]; then cp "$PREVIOUS/VERSION" "$PREBACK/PREVIOUS_VERSION"; fi
    sha256sum "$PREBACK/database.dump" > "$PREBACK/SHA256SUMS"
    chmod 750 "$PREBACK"; chmod 640 "$PREBACK"/* 2>/dev/null || true
    echo "PRE_UPGRADE_BACKUP_OK: $PREBACK"
  fi
fi

install -m 0640 "$RELEASE/deploy/infra/compose.yml" "$INFRA/compose.yml"
docker compose -f "$INFRA/compose.yml" up -d postgres
for _ in $(seq 1 30); do
  STATUS=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' server-oficina-postgres 2>/dev/null || true)
  [[ "$STATUS" == "healthy" ]] && break
  sleep 2
done
[[ "${STATUS:-}" == "healthy" ]] || { docker logs --tail=100 server-oficina-postgres; exit 4; }

DBPASS=$(cat "$DATA/secrets/postgres_password")
APP_HOST=127.0.0.1
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q '^Status: active'; then APP_HOST=0.0.0.0; fi
DBPASS_URL=$(DBPASS="$DBPASS" python3 - <<'PY'
import os
from urllib.parse import quote_plus
print(quote_plus(os.environ['DBPASS']))
PY
)
cat > "$CONF/server-oficina.env" <<ENV
SERVER_OFICINA_ENV=production
SERVER_OFICINA_DATABASE_URL=postgresql+psycopg://serveroficina:${DBPASS_URL}@127.0.0.1:5432/server_oficina
SERVER_OFICINA_DATA_DIR=/srv/server-oficina/data/app
SERVER_OFICINA_SESSION_HOURS=12
SERVER_OFICINA_COOKIE_SECURE=false
SERVER_OFICINA_HOST=${APP_HOST}
SERVER_OFICINA_PORT=8080
ENV
chown root:"$SERVICE_GROUP" "$CONF/server-oficina.env"
chmod 640 "$CONF/server-oficina.env"
chown -R "$SERVICE_USER":"$SERVICE_GROUP" "$DATA/data/app"
chmod 2770 "$DATA/data/app"

install -m 0644 "$RELEASE/deploy/server-oficina.service" /etc/systemd/system/server-oficina.service
install -m 0644 "$RELEASE/deploy/server-oficina-backup.service" /etc/systemd/system/server-oficina-backup.service
install -m 0644 "$RELEASE/deploy/server-oficina-backup.timer" /etc/systemd/system/server-oficina-backup.timer
systemctl daemon-reload

# Promoción controlada: si el health check falla, se recupera el current previo.
ln -sfn "$RELEASE" "$CURRENT"
systemctl enable server-oficina >/dev/null 2>&1 || true
systemctl restart server-oficina
systemctl enable --now server-oficina-backup.timer
sleep 3
if ! curl -fsS http://127.0.0.1:8080/api/health | python3 -m json.tool; then
  echo "HEALTH_FAIL: intentando rollback de release" >&2
  journalctl -u server-oficina -n 100 --no-pager >&2 || true
  if [[ -n "$PREVIOUS" && -d "$PREVIOUS" ]]; then
    ln -sfn "$PREVIOUS" "$CURRENT"
    systemctl restart server-oficina || true
    sleep 2
    curl -fsS http://127.0.0.1:8080/api/health >/dev/null 2>&1 && echo "ROLLBACK_RELEASE_OK: $PREVIOUS" >&2 || true
  fi
  exit 5
fi

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q '^Status: active'; then "$RELEASE/scripts/configurar-acceso-lan.sh" || true; fi
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then "$RELEASE/scripts/install-desktop-launchers.sh" || true; fi
IP=$(hostname -I | awk '{print $1}')
echo "Instalado: Server Oficina $VERSION"
echo "Release actual: $(readlink -f "$CURRENT")"
echo "Local: http://127.0.0.1:8080"
if [[ "$APP_HOST" == "0.0.0.0" ]]; then echo "LAN:   http://${IP:-IP_DE_LA_TABLET}:8080 (UFW activo; revisar regla de subred)"; else echo "LAN:   NO habilitada: UFW no estaba activo"; fi
echo "NAS/evidencias: configure desde la UI; no hay rutas de campamento hardcodeadas."
