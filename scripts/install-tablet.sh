#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "Ejecute con sudo/root" >&2; exit 1; fi
SRC=$(cd "$(dirname "$0")/.." && pwd)
TRUST_LAN=0
for arg in "$@"; do
  case "$arg" in
    --confiar-red-actual) TRUST_LAN=1 ;;  # decisión explícita: confiar en la red actual
    *) echo "Uso: $0 [--confiar-red-actual]" >&2; exit 2 ;;
  esac
done
# shellcheck source=scripts/lib-release.sh
source "$SRC/scripts/lib-release.sh"
VERSION=$(tr -d '[:space:]' < "$SRC/VERSION")
STAMP=$(date +%Y%m%d-%H%M%S)
RELEASE_ID=$(release_id "$SRC" "$STAMP")
RELEASE=/opt/server-oficina/releases/$RELEASE_ID
CURRENT=/opt/server-oficina/current
CONF=/etc/server-oficina
DATA=/srv/server-oficina
INFRA=$DATA/app/infra
FILES=$DATA/files
VERSIONS=$DATA/versions
SERVICE_USER=serveroficina
SERVICE_GROUP=serveroficina
LOCAL_CLOUD=server-oficina-local-cloud
# `readlink -f` devuelve la ruta aunque no exista: sin este control una primera
# instalación tomaría `current` como su propia release previa y un rollback lo
# convertiría en un symlink en bucle.
PREVIOUS=""
if [[ -L "$CURRENT" ]]; then PREVIOUS=$(readlink -f "$CURRENT" 2>/dev/null || true); fi
if [[ -n "$PREVIOUS" && ! -d "$PREVIOUS" ]]; then
  echo "AVISO: current apunta a una release inexistente ($PREVIOUS); no hay rollback posible" >&2
  PREVIOUS=""
fi
LOCAL_CLOUD_WAS_ENABLED=$(systemctl is-enabled "$LOCAL_CLOUD" 2>/dev/null || true)

# Nunca sobrescribir la release activa ni reutilizar un directorio instalado.
assert_new_release "$RELEASE" "$PREVIOUS" || exit 6
echo "Release nueva: $RELEASE_ID"
echo "Release activa previa: ${PREVIOUS:-NINGUNA}"

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

# Carpetas de Nube Local (modelo de permisos en docs/arquitectura/53):
#   files/     root:serveroficina 2750  la app sólo LEE; escribe Syncthing del hub
#   versions/  serveroficina      2750  sólo el observador escribe el historial
# Sólo se crean si faltan: nunca se cambia (ni recursivamente) el dueño de una
# carpeta existente porque Syncthing del hub puede depender de sus permisos.
if [[ ! -d "$FILES" ]]; then
  install -d -o root -g "$SERVICE_GROUP" -m 2750 "$FILES"
  echo "CREADO: $FILES"
fi
if [[ ! -d "$VERSIONS" ]]; then
  install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 2750 "$VERSIONS"
  echo "CREADO: $VERSIONS"
fi
runuser -u "$SERVICE_USER" -- test -w "$VERSIONS" || { echo "$VERSIONS no es escribible por $SERVICE_USER" >&2; exit 8; }
runuser -u "$SERVICE_USER" -- test -r "$FILES" -a -x "$FILES" || { echo "$FILES no es legible por $SERVICE_USER" >&2; exit 8; }

# Copiar y validar la nueva release ANTES de tocar el puntero current. El código
# queda de root y sin escritura de grupo/otros: rsync -a como root conservaría
# el dueño del checkout (p. ej. adminoficina) y lo haría editable en producción.
rsync -a --chown=root:root --chmod=Dgo-w,Fgo-w --exclude '.git' --exclude '.venv' --exclude 'venv' --exclude '__pycache__' --exclude '*.pyc' \
  --exclude '.pytest_cache' --exclude 'runtime' --exclude 'tests/test.db' --exclude 'tests/runtime' \
  --exclude '.env' "$SRC/" "$RELEASE/"
cat > "$RELEASE/RELEASE_INFO" <<INFO
release_id=$RELEASE_ID
version=$VERSION
git_commit=$(git -c safe.directory="$SRC" -C "$SRC" rev-parse HEAD 2>/dev/null || echo desconocido)
installed_at=$STAMP
installed_by=${SUDO_USER:-root}
previous_release=${PREVIOUS:-NINGUNA}
INFO
python3 -m venv "$RELEASE/.venv"
"$RELEASE/.venv/bin/pip" install --upgrade pip
"$RELEASE/.venv/bin/pip" install -r "$RELEASE/requirements-dev.txt"
( cd "$RELEASE" && ./scripts/verify-package.sh )

# PostgreSQL arriba y sano ANTES del respaldo: un contenedor detenido no debe
# dejar la actualización sin backup ni saltárselo en silencio.
install -m 0640 "$RELEASE/deploy/infra/compose.yml" "$INFRA/compose.yml"
docker compose -f "$INFRA/compose.yml" up -d postgres
for _ in $(seq 1 30); do
  STATUS=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' server-oficina-postgres 2>/dev/null || true)
  [[ "$STATUS" == "healthy" ]] && break
  sleep 2
done
[[ "${STATUS:-}" == "healthy" ]] || { docker logs --tail=100 server-oficina-postgres; exit 4; }

# Backup pre-upgrade real y verificable (siempre; un fallo de pg_dump aborta
# antes de tocar `current`).
PREBACK="$DATA/backups/server-oficina/pre-upgrade-${VERSION}-${STAMP}"
mkdir -p "$PREBACK"
docker exec server-oficina-postgres pg_dump -U serveroficina -d server_oficina -Fc > "$PREBACK/database.dump"
if [[ -n "$PREVIOUS" && -f "$PREVIOUS/VERSION" ]]; then cp "$PREVIOUS/VERSION" "$PREBACK/PREVIOUS_VERSION"; fi
echo "${PREVIOUS:-NINGUNA}" > "$PREBACK/PREVIOUS_RELEASE"
echo "$RELEASE_ID" > "$PREBACK/NEW_RELEASE_ID"
( cd "$PREBACK" && sha256sum database.dump > SHA256SUMS )  # rutas relativas: verificable fuera del host
chmod 750 "$PREBACK"; chmod 640 "$PREBACK"/* 2>/dev/null || true
echo "PRE_UPGRADE_BACKUP_OK: $PREBACK"

DBPASS=$(cat "$DATA/secrets/postgres_password")
# Fail-closed: la API se instala sólo en loopback. configurar-acceso-lan.sh la
# publica en la LAN únicamente tras demostrar firewall + red confiable.
APP_HOST=127.0.0.1
LAN_EXPECTED=0
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q '^Status: active'; then LAN_EXPECTED=1; fi
DBPASS_URL=$(DBPASS="$DBPASS" python3 - <<'PY'
import os
from urllib.parse import quote_plus
print(quote_plus(os.environ['DBPASS']))
PY
)
ENV_FILE=$CONF/server-oficina.env
ENV_OLD=""
if [[ -f "$ENV_FILE" ]]; then
  ENV_OLD=$CONF/server-oficina.env.pre-$STAMP
  cp -p "$ENV_FILE" "$ENV_OLD"
fi
cat > "$ENV_FILE" <<ENV
SERVER_OFICINA_ENV=production
SERVER_OFICINA_DATABASE_URL=postgresql+psycopg://serveroficina:${DBPASS_URL}@127.0.0.1:5432/server_oficina
SERVER_OFICINA_DATA_DIR=/srv/server-oficina/data/app
SERVER_OFICINA_SYNC_ROOT=$FILES
SERVER_OFICINA_VERSIONS_ROOT=$VERSIONS
SERVER_OFICINA_SESSION_HOURS=12
SERVER_OFICINA_COOKIE_SECURE=false
SERVER_OFICINA_HOST=${APP_HOST}
SERVER_OFICINA_PORT=8080
ENV
# Ajustes agregados por el operador (p. ej. API de Syncthing) sobreviven a la actualización.
MANAGED='^(SERVER_OFICINA_ENV|SERVER_OFICINA_DATABASE_URL|SERVER_OFICINA_DATA_DIR|SERVER_OFICINA_SYNC_ROOT|SERVER_OFICINA_VERSIONS_ROOT|SERVER_OFICINA_SESSION_HOURS|SERVER_OFICINA_COOKIE_SECURE|SERVER_OFICINA_HOST|SERVER_OFICINA_PORT)='
if [[ -n "$ENV_OLD" ]]; then
  grep -E '^[A-Z_][A-Z0-9_]*=' "$ENV_OLD" | grep -Ev "$MANAGED" >> "$ENV_FILE" || true
fi
chown root:"$SERVICE_GROUP" "$ENV_FILE"
chmod 640 "$ENV_FILE"
chown -R "$SERVICE_USER":"$SERVICE_GROUP" "$DATA/data/app"
chmod 2770 "$DATA/data/app"

install -m 0644 "$RELEASE/deploy/server-oficina.service" /etc/systemd/system/server-oficina.service
install -m 0644 "$RELEASE/deploy/server-oficina-backup.service" /etc/systemd/system/server-oficina-backup.service
install -m 0644 "$RELEASE/deploy/server-oficina-backup.timer" /etc/systemd/system/server-oficina-backup.timer
install -m 0644 "$RELEASE/deploy/$LOCAL_CLOUD.service" "/etc/systemd/system/$LOCAL_CLOUD.service"
systemctl daemon-reload

# Cambio atómico del puntero: nunca existe un instante sin `current`.
swap_current() {
  ln -sfn "$1" "$CURRENT.new"
  mv -Tf "$CURRENT.new" "$CURRENT"
}

wait_health() {
  for _ in $(seq 1 20); do
    curl -fsS http://127.0.0.1:8080/api/health >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

rollback() {
  echo "$1: intentando rollback de release" >&2
  if [[ -n "$PREVIOUS" && -d "$PREVIOUS" ]]; then
    swap_current "$PREVIOUS"
    # La release previa vuelve con su configuración previa (incluido el host).
    if [[ -n "$ENV_OLD" && -f "$ENV_OLD" ]]; then cp -p "$ENV_OLD" "$ENV_FILE"; fi
  fi
  # El observador vuelve a su estado previo; una release sin worker no puede ejecutarlo.
  if [[ "$LOCAL_CLOUD_WAS_ENABLED" != "enabled" || -z "$PREVIOUS" || ! -f "$PREVIOUS/app/workers/local_cloud_worker.py" ]]; then
    systemctl disable --now "$LOCAL_CLOUD" >/dev/null 2>&1 || true
  fi
  if [[ -n "$PREVIOUS" && -d "$PREVIOUS" ]]; then
    systemctl restart server-oficina || true
    if wait_health; then echo "ROLLBACK_RELEASE_OK: $PREVIOUS" >&2; else echo "ROLLBACK_HEALTH_FAIL: $PREVIOUS" >&2; fi
  fi
}

# Promoción controlada: si el health check falla, se recupera el current previo.
swap_current "$RELEASE"
systemctl enable server-oficina >/dev/null 2>&1 || true
systemctl restart server-oficina
systemctl enable --now server-oficina-backup.timer
if ! wait_health || ! curl -fsS http://127.0.0.1:8080/api/health | python3 -m json.tool; then
  journalctl -u server-oficina -n 100 --no-pager >&2 || true
  rollback HEALTH_FAIL
  exit 5
fi

# Observador Nube Local: sólo tras health OK y verificando que no quede en
# bucle de reinicios (RestartSec=5). No borra archivos de trabajo.
systemctl enable "$LOCAL_CLOUD" >/dev/null
systemctl restart "$LOCAL_CLOUD"
LC_BASE=$(systemctl show -p NRestarts --value "$LOCAL_CLOUD" 2>/dev/null || true)
sleep 8
LC_STATE=$(systemctl is-active "$LOCAL_CLOUD" 2>/dev/null || true)
LC_NOW=$(systemctl show -p NRestarts --value "$LOCAL_CLOUD" 2>/dev/null || true)
# Delta de reinicios automáticos desde el restart manual (no depende de si
# systemd reinicia o no el contador en un restart explícito).
if [[ "$LC_BASE" =~ ^[0-9]+$ && "$LC_NOW" =~ ^[0-9]+$ ]]; then
  LC_RESTARTS=$((LC_NOW - LC_BASE))
else
  LC_RESTARTS="?"
fi
if [[ "$LC_STATE" != "active" || "$LC_RESTARTS" != "0" ]]; then
  echo "LOCAL_CLOUD_FAIL: estado=$LC_STATE reinicios=$LC_RESTARTS" >&2
  journalctl -u "$LOCAL_CLOUD" -n 50 --no-pager >&2 || true
  rollback LOCAL_CLOUD_FAIL
  exit 7
fi
echo "LOCAL_CLOUD_OK: $LOCAL_CLOUD activo"

LAN_STATUS="NO habilitada: UFW no está activo (Server Oficina sólo en 127.0.0.1)"
LAN_RC=0
if [[ $LAN_EXPECTED == 1 ]]; then
  LAN_ARGS=()
  [[ $TRUST_LAN == 1 ]] && LAN_ARGS+=(--confiar-red-actual)
  if "$RELEASE/scripts/configurar-acceso-lan.sh" "${LAN_ARGS[@]}"; then
    LAN_STATUS="PUBLICADA sólo en la subred de la red confiable actual"
  else
    LAN_RC=$?
    LAN_STATUS="NO publicada (código $LAN_RC): ver LAN_NO_PUBLICADA arriba"
  fi
fi
# Defensa en profundidad: sin publicación verificada la API jamás queda en 0.0.0.0.
if [[ "$LAN_STATUS" != PUBLICADA* ]] && ! grep -qx 'SERVER_OFICINA_HOST=127.0.0.1' "$ENV_FILE"; then
  sed -i 's/^SERVER_OFICINA_HOST=.*/SERVER_OFICINA_HOST=127.0.0.1/' "$ENV_FILE"
  systemctl restart server-oficina
fi
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then "$RELEASE/scripts/install-desktop-launchers.sh" || true; fi
IP=$(hostname -I | awk '{print $1}')
echo "Instalado: Server Oficina $VERSION ($RELEASE_ID)"
echo "Release actual: $(readlink -f "$CURRENT")"
echo "Release previa conservada para rollback: ${PREVIOUS:-NINGUNA}"
echo "Local: http://127.0.0.1:8080"
echo "LAN:   $LAN_STATUS"
[[ "$LAN_STATUS" == PUBLICADA* ]] && echo "       http://${IP:-IP_DE_LA_TABLET}:8080"
echo "NAS/evidencias: configure desde la UI; no hay rutas de campamento hardcodeadas."
if [[ $LAN_EXPECTED == 1 && "$LAN_STATUS" != PUBLICADA* ]]; then
  # Se esperaba publicar en la LAN y no pudo demostrarse: no se declara sana.
  echo "INSTALACION_SOLO_LOCAL: release sana en 127.0.0.1, LAN no publicada." >&2
  echo "Tras verificar la red: sudo $RELEASE/scripts/configurar-acceso-lan.sh --confiar-red-actual" >&2
  exit 10
fi
