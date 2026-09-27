#!/usr/bin/env bash
# Evidencia PRE/POST de la Latitude. SÓLO LECTURA: no instala, no reinicia,
# no cambia permisos. Lo único que escribe es el propio archivo de evidencia en
# el HOME del operador. Nunca imprime contraseñas: el env se muestra con valores
# redactados y el secreto de PostgreSQL no se lee.
#
# Uso (desde la copia candidata):   sudo ./scripts/evidencia-latitude.sh PRE
#                                   sudo ./scripts/evidencia-latitude.sh POST
set -uo pipefail
LABEL=${1:-PRE}
[[ "$LABEL" =~ ^[A-Z0-9_-]+$ ]] || { echo "Etiqueta inválida: $LABEL" >&2; exit 1; }
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "Ejecute con sudo (lectura de systemd/docker/ufw)" >&2; exit 1; fi
SRC=$(cd "$(dirname "$0")/.." && pwd)
STAMP=$(date +%Y%m%d-%H%M%S)
OWNER=${SUDO_USER:-root}
OUTDIR=$(getent passwd "$OWNER" | cut -d: -f6)/server-oficina-evidencia
mkdir -p "$OUTDIR"
OUT=$OUTDIR/$LABEL-$STAMP.txt
DATA=/srv/server-oficina
CURRENT=/opt/server-oficina/current

run() {
  printf '\n$ %s\n' "$*"
  timeout 30 bash -c "$*" 2>&1
  printf '[rc=%s]\n' "$?"
}

{
  echo "SERVER OFICINA · EVIDENCIA $LABEL · $(date -Is)"
  echo "operador=$OWNER candidata=$SRC"
  echo
  echo "== Identidad y red (Ethernet + Wi-Fi pueden estar activas a la vez) =="
  run hostname
  run hostname -I
  run ip -br addr
  run ip -br link
  run ip -4 route
  run "ip -4 route show default"
  run "for i in /sys/class/net/*; do n=\${i##*/}; printf '%-16s device=%s wireless=%s master=%s oper=%s\n' \"\$n\" \"\$([[ -e \$i/device ]] && echo si || echo no)\" \"\$([[ -e \$i/wireless || -e \$i/phy80211 ]] && echo si || echo no)\" \"\$([[ -e \$i/master ]] && basename \"\$(readlink -f \$i/master)\" || echo -)\" \"\$(cat \$i/operstate)\"; done"
  run "ip -4 neigh show"
  run "nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev 2>/dev/null || echo 'nmcli no disponible'"
  run "nmcli -t -f DEVICE,UUID,NAME connection show --active 2>/dev/null || true"
  run "iw dev 2>/dev/null | grep -E 'Interface|ssid' || true"
  echo; echo "== Descubrimiento local (mDNS/Avahi) y no-enrutamiento =="
  run "getent hosts server-oficina.local || echo 'server-oficina.local NO resuelve (desde la propia Latitude)'"
  run "systemctl is-active avahi-daemon || true"
  run "grep -Ev '^[[:space:]]*(#|;|$)' /etc/avahi/avahi-daemon.conf 2>/dev/null || echo 'sin /etc/avahi/avahi-daemon.conf'"
  run "journalctl -u avahi-daemon -n 30 --no-pager 2>/dev/null | grep -Ei 'registering|conflict|joining|server startup' || true"
  run "sysctl net.ipv4.ip_forward"
  run "iptables -S FORWARD 2>/dev/null | head -3 || true"
  run "grep -E '^DEFAULT_FORWARD_POLICY' /etc/default/ufw 2>/dev/null || true"
  run "grep -n '224.0.0.251' /etc/ufw/before.rules 2>/dev/null || echo 'before.rules sin regla mDNS genérica'"
  run "ip -d link show type bridge 2>/dev/null || true"
  run "python3 $CURRENT/scripts/lan_firewall.py audit 2>/dev/null || python3 $SRC/scripts/lan_firewall.py audit 2>/dev/null || echo 'auditoría LAN no disponible'"
  run timedatectl

  echo; echo "== Release activa vs candidata =="
  run "cat $CURRENT/VERSION"
  run "readlink -f $CURRENT || true"
  run "cat $CURRENT/RELEASE_INFO 2>/dev/null || echo 'sin RELEASE_INFO (instalada con el esquema releases/<VERSION>)'"
  run "ls -lah /opt/server-oficina/releases/"
  run "du -sh /opt/server-oficina/releases/* 2>/dev/null | tail -10"
  run "stat -c '%U:%G %a %n' $CURRENT/ $CURRENT/app 2>/dev/null || true"
  run "cat $SRC/VERSION"
  run "git -c safe.directory=$SRC -C $SRC rev-parse HEAD 2>/dev/null || echo 'candidata sin git'"
  run "git -c safe.directory=$SRC -C $SRC status --short --untracked-files=no 2>/dev/null | head -20"
  # Colisión: ¿la candidata usaría el mismo directorio que la release activa?
  # shellcheck source=scripts/lib-release.sh
  source "$SRC/scripts/lib-release.sh"
  NEXT=/opt/server-oficina/releases/$(release_id "$SRC" "$STAMP" 2>/dev/null || echo INVALIDA)
  echo "release que crearía el instalador: $NEXT"
  if assert_new_release "$NEXT" "$(readlink -f "$CURRENT" 2>/dev/null || true)" 2>&1; then
    echo "COLISION_RELEASE: NO"
  else
    echo "COLISION_RELEASE: SI -> no instalar"
  fi
  LEGACY=/opt/server-oficina/releases/$(tr -d '[:space:]' < "$SRC/VERSION")
  if [[ "$(readlink -f "$CURRENT" 2>/dev/null)" == "$LEGACY" ]]; then
    echo "AVISO: la release activa usa el nombre legado $LEGACY; el instalador anterior la habría sobrescrito en caliente."
  fi

  echo; echo "== Servicios =="
  run "systemctl status server-oficina --no-pager -l | head -25"
  run "systemctl status server-oficina-backup.timer --no-pager | head -15"
  run "systemctl status server-oficina-local-cloud --no-pager -l | head -25 || true"
  run "systemctl is-enabled server-oficina server-oficina-backup.timer server-oficina-local-cloud 2>&1"
  run "systemctl show -p NRestarts,MemoryCurrent,CPUUsageNSec,ActiveEnterTimestamp server-oficina server-oficina-local-cloud"
  run "systemctl list-timers --all --no-pager | grep -i server-oficina || true"
  run "journalctl -u server-oficina -n 40 --no-pager"
  run "journalctl -u server-oficina-local-cloud -n 40 --no-pager 2>/dev/null || true"

  echo; echo "== PostgreSQL / Docker =="
  run "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
  run "docker inspect server-oficina-postgres --format 'estado={{.State.Status}} salud={{if .State.Health}}{{.State.Health.Status}}{{end}} reinicios={{.RestartCount}} inicio={{.State.StartedAt}} imagen={{.Config.Image}}'"
  run "docker inspect server-oficina-postgres --format '{{json .Mounts}}'"
  run "docker inspect server-oficina-postgres --format '{{json .HostConfig.PortBindings}}'"
  run "docker exec server-oficina-postgres pg_isready -U serveroficina -d server_oficina"
  run "docker exec server-oficina-postgres psql -U serveroficina -d server_oficina -Atc \"select count(*) from information_schema.tables where table_schema='public'\""

  echo; echo "== Salud de la aplicación =="
  run "curl -fsS http://127.0.0.1:8080/api/health | python3 -m json.tool"

  echo; echo "== Backups =="
  run "ls -la $DATA/backups/server-oficina | tail -8"
  LAST=$(ls -1d "$DATA"/backups/server-oficina/2* 2>/dev/null | tail -1)
  if [[ -n "$LAST" ]]; then run "cd '$LAST' && sha256sum -c SHA256SUMS"; run "cat '$LAST/BACKUP_INFO' 2>/dev/null || echo 'respaldo sin BACKUP_INFO (formato previo)'"; fi
  run "cat /etc/server-oficina/backup.env 2>/dev/null || echo 'sin backup.env: versions/ sin réplica externa'"

  echo; echo "== Almacenamiento =="
  run df -h
  run df -i
  run lsblk -o NAME,SIZE,TYPE,MOUNTPOINTS
  run "vgs 2>/dev/null || true"
  run "free -h"
  run uptime
  run "find $DATA -maxdepth 2 -type d -printf '%M %u:%g %p\n' | sort -k3"
  run "du -sh $DATA/files $DATA/versions 2>/dev/null || true"
  run "find $DATA/versions -type f 2>/dev/null | wc -l"

  echo; echo "== Configuración (valores redactados) =="
  run "sed -E 's/=.*/=<redactado>/' /etc/server-oficina/server-oficina.env"
  run "ls -la /etc/server-oficina/"

  echo; echo "== Syncthing / firewall =="
  run "command -v syncthing && syncthing --version || echo 'syncthing NO instalado'"
  run "pgrep -a syncthing || echo 'syncthing no está corriendo'"
  run "systemctl list-units --all --no-pager 'syncthing*' || true"
  run "ss -tulpn | grep -E ':(8080|8384|22000|21027|5353)\b' || true"
  run "ufw status verbose"
  run "ufw status numbered"
  run "python3 $CURRENT/scripts/lan_firewall.py status 2>/dev/null || echo 'reconciliador LAN no disponible en la release activa'"
  run "systemctl status server-oficina-lan-firewall.timer --no-pager 2>/dev/null | head -8 || true"
} > "$OUT"

chown "$OWNER": "$OUTDIR" "$OUT" 2>/dev/null || true
chmod 600 "$OUT"
sha256sum "$OUT" | tee "$OUT.sha256"
echo "EVIDENCIA_$LABEL: $OUT"
