#!/usr/bin/env bash
# Restauración administrativa explícita. Ver docs/operacion/36_BACKUP_RESTORE.md.
#
# Garantía: nunca queda una base "a medias" anunciada como restaurada.
#   1. Validación (salida 20): SHA256SUMS, lectura COMPLETA del dump
#      (pg_restore -f /dev/null) y del tar (tar -tzf, sólo imports/ y evidence/).
#   2. Preparación (salida 21): el dump se restaura en una base NUEVA
#      (server_oficina_restore_<fecha>) con --single-transaction --exit-on-error:
#      o entra entero o no entra nada. Los archivos se extraen a
#      data/app/.restore-staging-<fecha>. Hasta aquí la base viva, data/app y los
#      servicios NO se tocan.
#   3. Intercambio: con la API y el observador detenidos, un único COMMIT
#      renombra server_oficina -> server_oficina_pre_restore_<fecha> y la base
#      preparada -> server_oficina. imports/ y evidence/ vivos se MUEVEN (nunca
#      se borran) a data/app/.pre-restore-<fecha>/ y los preparados ocupan su lugar.
#   4. Health: si la API no responde, se deshace el intercambio completo
#      (salida 22). Si no se puede deshacer, salida 23 con servicios detenidos.
# Resultado en /srv/server-oficina/backups/restore-logs/restore-<fecha>.txt.
#
# Códigos: 0 RESTORE_OK · 1 uso · 20 validación · 21 preparación (nada tocado)
#          22 health/intercambio fallido y revertido · 23 CRÍTICO, intervención manual
#          24 restaurado y sano pero el observador no volvió a arrancar
set -euo pipefail
umask 027
if [[ $# -ne 1 ]]; then echo "Uso: sudo $0 /srv/server-oficina/backups/server-oficina/AAAAMMDD-HHMMSS" >&2; exit 1; fi
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "Ejecute con sudo/root" >&2; exit 1; fi
ARG=$1

PG=server-oficina-postgres
DB=server_oficina
API=server-oficina
LOCAL_CLOUD=server-oficina-local-cloud
APP=/srv/server-oficina/data/app
APP_DIRS=(imports evidence)
LOG_DIR=/srv/server-oficina/backups/restore-logs
STAMP=$(date +%Y%m%d%H%M%S)
STAGE_DB=${DB}_restore_$STAMP
PREV_DB=${DB}_pre_restore_$STAMP
STAGE_APP=$APP/.restore-staging-$STAMP
PREV_APP=$APP/.pre-restore-$STAMP
mkdir -p "$LOG_DIR"
RESULT=$LOG_DIR/restore-$STAMP.txt
[[ -e "$RESULT" ]] && RESULT=$(mktemp --suffix=.txt "$LOG_DIR/restore-$STAMP-XXXX")

PHASE=validacion      # validacion | preparacion | intercambio | hecho
STAGE_DB_CREATED=0
STAGE_APP_CREATED=0
DB_SWAPPED=0
MOVED_PREV=()         # dirs de data/app movidos a PREV_APP
MOVED_NEW=()          # dirs preparados colocados en data/app
API_WAS_ACTIVE=inactive
LC_WAS_ACTIVE=inactive
FINISHED=0

log() { echo "[restore $(date +%H:%M:%S)] $*"; }
pgsql() { docker exec "$PG" psql -U serveroficina -d postgres -v ON_ERROR_STOP=1 -Atq "$@"; }
db_exists() { [[ "$(pgsql -c "SELECT 1 FROM pg_database WHERE datname = '$1'")" == 1 ]]; }
wait_health() {
  for _ in $(seq 1 30); do
    curl -fsS http://127.0.0.1:8080/api/health >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

write_result() {  # write_result CÓDIGO ESTADO DETALLE
  {
    echo "resultado=$2"
    echo "codigo=$1"
    echo "detalle=$3"
    echo "fecha=$STAMP"
    echo "respaldo=${BACKUP:-$ARG}"
    echo "fase=$PHASE"
    echo "base_activa=$DB"
    echo "base_previa=$([[ $DB_SWAPPED == 1 ]] && echo "$PREV_DB" || echo ninguna)"
    echo "archivos_previos=$([[ ${#MOVED_PREV[@]} -gt 0 ]] && echo "$PREV_APP" || echo ninguno)"
    echo "servicio_api=$(systemctl is-active "$API" 2>/dev/null || true)"
    echo "servicio_observador=$(systemctl is-active "$LOCAL_CLOUD" 2>/dev/null || true)"
  } > "$RESULT"
}

finish() {  # finish CÓDIGO ESTADO DETALLE
  FINISHED=1
  trap - EXIT
  write_result "$1" "$2" "$3"
  if [[ $1 == 0 ]]; then
    echo "$2: $3"
  else
    echo "$2: $3" >&2
  fi
  echo "Resultado: $RESULT" >&2
  exit "$1"
}

drop_staging() {  # sólo lo que este proceso creó con nombre único
  if [[ $STAGE_DB_CREATED == 1 ]]; then
    pgsql -c "DROP DATABASE IF EXISTS $STAGE_DB WITH (FORCE)" >/dev/null || log "no se pudo eliminar la base temporal $STAGE_DB"
  fi
  if [[ $STAGE_APP_CREATED == 1 && -d "$STAGE_APP" ]]; then
    rm -rf --one-file-system "$STAGE_APP"
  fi
}

swap_databases() {  # swap_databases ACTUAL_A_APARTAR NOMBRE_APARTADO ENTRANTE
  # Un único COMMIT: o se renombran las dos o ninguna. Las sesiones abiertas
  # sobre la base activa se terminan (la API y el observador ya están detenidos).
  local attempt
  for attempt in 1 2 3; do
    pgsql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('$1', '$3') AND pid <> pg_backend_pid()" >/dev/null || true
    if pgsql -c "BEGIN; ALTER DATABASE $1 RENAME TO $2; ALTER DATABASE $3 RENAME TO $1; COMMIT;" >/dev/null; then
      return 0
    fi
    log "intercambio de bases rechazado (intento $attempt); reintentando"
    sleep 2
  done
  return 1
}

start_services() {  # arranca la API (y el observador si estaba activo); 0 si la API está sana
  systemctl start "$API" || return 1
  wait_health || return 1
  if [[ "$LC_WAS_ACTIVE" == active ]]; then systemctl start "$LOCAL_CLOUD" || true; fi
  return 0
}

revert() {  # deshace el intercambio; sale con 22 si todo quedó como antes, 23 si no
  local reason=$1 ok=1 d
  log "REVERTIR: $reason"
  systemctl stop "$LOCAL_CLOUD" 2>/dev/null || true
  systemctl stop "$API" 2>/dev/null || true
  if [[ $DB_SWAPPED == 1 ]]; then
    if swap_databases "$DB" "$STAGE_DB" "$PREV_DB"; then
      DB_SWAPPED=0
      STAGE_DB_CREATED=1  # la copia restaurada vuelve a ser la base temporal: se descarta
    else
      ok=0; log "no se pudo devolver $PREV_DB a $DB"
    fi
  fi
  for d in "${MOVED_NEW[@]}"; do
    mv "$APP/$d" "$STAGE_APP/$d" || { ok=0; log "no se pudo apartar $APP/$d restaurado"; }
  done
  MOVED_NEW=()
  if (( ok )); then
    for d in "${MOVED_PREV[@]}"; do
      mv "$PREV_APP/$d" "$APP/$d" || { ok=0; log "no se pudo devolver $PREV_APP/$d"; }
    done
    if (( ok )); then MOVED_PREV=(); rmdir "$PREV_APP" 2>/dev/null || true; fi
  fi
  if (( ! ok )); then
    finish 23 RESTORE_FAIL_CRITICO "$reason; la vuelta atrás NO se completó. Servicios detenidos a propósito. Estado: base activa=$DB, previa=$PREV_DB, preparada=$STAGE_DB, archivos previos en $PREV_APP. Intervención manual."
  fi
  drop_staging
  if ! start_services; then
    systemctl stop "$LOCAL_CLOUD" 2>/dev/null || true
    systemctl stop "$API" 2>/dev/null || true
    finish 23 RESTORE_FAIL_CRITICO "$reason; se restablecieron la base y los archivos previos, pero la API tampoco responde con ellos. Servicios detenidos a propósito. Intervención manual."
  fi
  [[ "$API_WAS_ACTIVE" == active ]] || systemctl stop "$API" || true
  finish 22 RESTORE_FAIL "$reason; se revirtió al estado previo (base y archivos intactos, servicios como antes). Nada se restauró."
}

on_exit() {
  local rc=$?
  [[ $FINISHED == 1 ]] && return
  case "$PHASE" in
    validacion) finish 20 RESTORE_FAIL "error inesperado ($rc) durante la validación; nada se tocó" ;;
    preparacion) drop_staging; finish 21 RESTORE_FAIL "error inesperado ($rc) durante la preparación; base viva, archivos y servicios intactos" ;;
    intercambio) revert "error inesperado ($rc) durante el intercambio" ;;
    hecho) finish 24 RESTORE_AVISO "error inesperado ($rc) tras una restauración ya verificada" ;;
  esac
}
trap on_exit EXIT

# ---------------------------------------------------------------- 1 · validación
exec 9>/run/server-oficina-restore.lock
flock -n 9 || finish 20 RESTORE_FAIL "otra restauración está en curso"
BACKUP=$(readlink -f "$1")
[[ -d "$BACKUP" ]] || finish 20 RESTORE_FAIL "respaldo inexistente: $BACKUP"
cd "$BACKUP"
[[ -f SHA256SUMS && -f database.dump ]] || finish 20 RESTORE_FAIL "faltan SHA256SUMS o database.dump en $BACKUP"
grep -Eq '[[:space:]]\*?database\.dump$' SHA256SUMS || finish 20 RESTORE_FAIL "database.dump no figura en SHA256SUMS"
if [[ -f app-files.tar.gz ]] && ! grep -Eq '[[:space:]]\*?app-files\.tar\.gz$' SHA256SUMS; then
  finish 20 RESTORE_FAIL "app-files.tar.gz no figura en SHA256SUMS"
fi
sha256sum --quiet --strict -c SHA256SUMS || finish 20 RESTORE_FAIL "SHA256SUMS no coincide: respaldo dañado o alterado"
pgsql -c "SELECT 1" >/dev/null || finish 20 RESTORE_FAIL "PostgreSQL ($PG) no responde"
db_exists "$DB" || finish 20 RESTORE_FAIL "no existe la base $DB; instale Server Oficina antes de restaurar"
id serveroficina >/dev/null 2>&1 || finish 20 RESTORE_FAIL "no existe el usuario serveroficina; instale Server Oficina antes de restaurar"
for name in "$STAGE_DB" "$PREV_DB"; do
  ! db_exists "$name" || finish 20 RESTORE_FAIL "ya existe la base $name; reintente en un segundo"
done
[[ ! -e "$STAGE_APP" && ! -e "$PREV_APP" ]] || finish 20 RESTORE_FAIL "ya existe $STAGE_APP o $PREV_APP"
log "leyendo el dump completo (sin escribir en ninguna base)"
docker exec -i "$PG" pg_restore -f /dev/null < database.dump \
  || finish 20 RESTORE_FAIL "database.dump ilegible o truncado (pg_restore no pudo leerlo entero)"
BACKUP_DIRS=()
if [[ -f app-files.tar.gz ]]; then
  MEMBERS=$(tar -tzf app-files.tar.gz) || finish 20 RESTORE_FAIL "app-files.tar.gz ilegible o truncado"
  while IFS= read -r member; do
    [[ -z "$member" ]] && continue
    top=${member%%/*}
    [[ "$member" != /* && "/$member/" != */../* && ( "$top" == imports || "$top" == evidence ) ]] \
      || finish 20 RESTORE_FAIL "app-files.tar.gz contiene una ruta no permitida: $member"
  done <<< "$MEMBERS"
  for d in "${APP_DIRS[@]}"; do grep -Eq "^$d(/|$)" <<< "$MEMBERS" && BACKUP_DIRS+=("$d"); done
fi
log "respaldo válido: $BACKUP"

# ---------------------------------------------------------------- 2 · preparación
PHASE=preparacion
pgsql -c "CREATE DATABASE $STAGE_DB TEMPLATE template0" >/dev/null \
  || finish 21 RESTORE_FAIL "no se pudo crear la base temporal $STAGE_DB"
STAGE_DB_CREATED=1
log "restaurando en la base temporal $STAGE_DB (una sola transacción)"
if ! docker exec -i "$PG" pg_restore -U serveroficina -d "$STAGE_DB" --single-transaction --exit-on-error --no-owner < database.dump; then
  drop_staging
  finish 21 RESTORE_FAIL "pg_restore falló en la base temporal; se descartó entera. La base viva, data/app y los servicios NO se tocaron"
fi
TABLES=$(docker exec "$PG" psql -U serveroficina -d "$STAGE_DB" -Atq -c "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
if [[ ! "$TABLES" =~ ^[0-9]+$ ]] || (( TABLES == 0 )); then
  drop_staging
  finish 21 RESTORE_FAIL "la base temporal quedó sin tablas; respaldo vacío. Nada se tocó"
fi
mkdir -p "$APP"
mkdir "$STAGE_APP"
STAGE_APP_CREATED=1
if [[ -f app-files.tar.gz ]]; then
  tar -C "$STAGE_APP" --no-same-owner -xzf app-files.tar.gz \
    || { drop_staging; finish 21 RESTORE_FAIL "no se pudieron extraer los archivos; nada se tocó"; }
  chown -R serveroficina:serveroficina "$STAGE_APP"
fi

# ---------------------------------------------------------------- 3 · intercambio
API_WAS_ACTIVE=$(systemctl is-active "$API" 2>/dev/null || true)
LC_WAS_ACTIVE=$(systemctl is-active "$LOCAL_CLOUD" 2>/dev/null || true)
PHASE=intercambio
systemctl stop "$LOCAL_CLOUD" 2>/dev/null || true
systemctl stop "$API"
swap_databases "$DB" "$PREV_DB" "$STAGE_DB" || revert "no se pudo intercambiar la base (sesiones abiertas)"
DB_SWAPPED=1
STAGE_DB_CREATED=0
mkdir "$PREV_APP"
chmod 0700 "$PREV_APP"
for d in "${APP_DIRS[@]}"; do
  if [[ -e "$APP/$d" ]]; then mv "$APP/$d" "$PREV_APP/$d"; MOVED_PREV+=("$d"); fi
done
for d in "${BACKUP_DIRS[@]}"; do
  mv "$STAGE_APP/$d" "$APP/$d"; MOVED_NEW+=("$d")
done
log "intercambio hecho; comprobando la API con los datos restaurados"
start_services || revert "la API no respondió /api/health con los datos restaurados"

# ---------------------------------------------------------------- 4 · hecho
PHASE=hecho
rmdir "$STAGE_APP" 2>/dev/null || true
if (( ${#MOVED_PREV[@]} )); then
  # Lo que existía y no está (o difiere) en el respaldo: conservado en PREV_APP.
  ( cd "$PREV_APP" && find "${MOVED_PREV[@]}" -type f | LC_ALL=C sort ) | while IFS= read -r f; do
    if [[ ! -e "$APP/$f" ]]; then echo "ausente_en_respaldo	$f"
    elif ! cmp -s "$PREV_APP/$f" "$APP/$f"; then echo "distinto_en_respaldo	$f"; fi
  done > "$PREV_APP/DIFERENCIAS_CON_RESPALDO.tsv"
  EXTRA=$(grep -c . "$PREV_APP/DIFERENCIAS_CON_RESPALDO.tsv" || true)
  log "data/app previo conservado en $PREV_APP ($EXTRA archivos ausentes o distintos en el respaldo; ver DIFERENCIAS_CON_RESPALDO.tsv)"
else
  rmdir "$PREV_APP"
fi

if [[ -x /opt/server-oficina/current/.venv/bin/python && -f /etc/server-oficina/server-oficina.env ]]; then
  /opt/server-oficina/current/scripts/verificar-historial.sh \
    || echo "AVISO: faltan o están dañados objetos de versions/; ver docs/operacion/36_BACKUP_RESTORE.md (réplica externa)" >&2
fi
if [[ -f syncthing-hub-identity.tar.gz ]]; then
  echo "Identidad Syncthing del hub disponible en $BACKUP/syncthing-hub-identity.tar.gz."
  echo "NO se aplica automáticamente: nunca deben operar dos hubs con la misma clave."
  echo "Procedimiento manual: docs/operacion/36_BACKUP_RESTORE.md#identidad-syncthing-del-hub"
fi
if [[ "$LC_WAS_ACTIVE" == active ]] && ! systemctl is-active --quiet "$LOCAL_CLOUD"; then
  finish 24 RESTORE_AVISO "base y archivos restaurados y API sana, pero $LOCAL_CLOUD no volvió a arrancar"
fi
finish 0 RESTORE_OK "respaldo $BACKUP restaurado y verificado por /api/health. Base previa conservada como $PREV_DB (borrar a mano tras verificar)."
