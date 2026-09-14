#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "Ejecute con sudo/root"; exit 1; fi
SRC=$(cd "$(dirname "$0")/.." && pwd)
APP=/opt/server-oficina
DATA=/var/lib/server-oficina
CONF=/etc/server-oficina
USER=serveroficina
DB=server_oficina
DBUSER=serveroficina

echo "[1/8] Paquetes base"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip postgresql postgresql-client rsync curl openssl
id -u "$USER" >/dev/null 2>&1 || useradd --system --home "$DATA" --shell /usr/sbin/nologin "$USER"
mkdir -p "$APP" "$DATA"/{imports,evidence,backups} "$CONF" /var/log/server-oficina
rsync -a --delete --exclude '.venv' --exclude 'runtime' --exclude 'tests/test.db' --exclude 'tests/runtime' "$SRC"/ "$APP"/
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install --upgrade pip
"$APP/.venv/bin/pip" install -r "$APP/requirements.txt"

echo "[2/8] PostgreSQL y configuración"
if [[ ! -f "$CONF/server-oficina.env" ]]; then
  DBPASS=$(openssl rand -hex 24)
  if su - postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='$DBUSER'\"" | grep -q 1; then
    su - postgres -c "psql -c \"ALTER USER $DBUSER WITH PASSWORD '$DBPASS';\""
  else
    su - postgres -c "psql -c \"CREATE USER $DBUSER WITH PASSWORD '$DBPASS';\""
  fi
  su - postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='$DB'\"" | grep -q 1 || su - postgres -c "createdb -O $DBUSER $DB"
  cat > "$CONF/server-oficina.env" <<ENV
SERVER_OFICINA_ENV=production
SERVER_OFICINA_DATABASE_URL=postgresql+psycopg://$DBUSER:$DBPASS@127.0.0.1:5432/$DB
SERVER_OFICINA_DATA_DIR=$DATA
SERVER_OFICINA_SESSION_HOURS=12
SERVER_OFICINA_COOKIE_SECURE=false
SERVER_OFICINA_HOST=0.0.0.0
SERVER_OFICINA_PORT=8080
ENV
  chmod 640 "$CONF/server-oficina.env"
else
  echo "Configuración existente preservada: $CONF/server-oficina.env"
fi
chown -R "$USER":"$USER" "$APP" "$DATA" /var/log/server-oficina
chown root:"$USER" "$CONF/server-oficina.env"
chmod 640 "$CONF/server-oficina.env"

echo "[3/8] systemd"
cp "$APP/deploy/server-oficina.service" /etc/systemd/system/server-oficina.service
systemctl daemon-reload
systemctl enable --now server-oficina

echo "[4/8] Health"
sleep 3
curl -fsS http://127.0.0.1:8080/api/health || { journalctl -u server-oficina -n 80 --no-pager; exit 2; }

echo "[5/8] Backup timer"
cp "$APP/deploy/server-oficina-backup.service" /etc/systemd/system/
cp "$APP/deploy/server-oficina-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now server-oficina-backup.timer

echo "[6/8] Permisos"
chmod 750 "$DATA" "$CONF"

echo "[7/8] Estado"
systemctl --no-pager --full status server-oficina | sed -n '1,20p'

echo "[8/8] Listo"
IP=$(hostname -I | awk '{print $1}')
echo "Abra: http://${IP:-IP_DE_LA_TABLET}:8080"
echo "La primera apertura pedirá crear el administrador."
