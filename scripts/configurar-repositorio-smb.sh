#!/usr/bin/env bash
set -euo pipefail
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Ejecute con sudo/root" >&2; exit 1; }
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y cifs-utils >/dev/null

read -rp "Código del repositorio (ej. NAS_CAMPAMENTO): " CODE
CODE=$(printf '%s' "$CODE" | tr '[:lower:] -' '[:upper:]__' | tr -cd 'A-Z0-9_.-')
[[ -n "$CODE" ]] || { echo "Código inválido" >&2; exit 2; }
read -rp "Ruta SMB/UNC en formato //servidor/recurso: " REMOTE
[[ "$REMOTE" == //*/* ]] || { echo "Ruta SMB inválida" >&2; exit 3; }
read -rp "Punto de montaje Linux [/mnt/server-oficina/$CODE]: " MOUNT_POINT
MOUNT_POINT=${MOUNT_POINT:-/mnt/server-oficina/$CODE}
read -rp "Usuario SMB: " SMB_USER
read -rp "Dominio (Enter si no aplica): " SMB_DOMAIN
read -srp "Contraseña SMB: " SMB_PASS; echo

mkdir -p /etc/server-oficina /mnt/server-oficina "$MOUNT_POINT"
CRED="/etc/server-oficina/smb-${CODE}.cred"
umask 077
{
  printf 'username=%s\n' "$SMB_USER"
  printf 'password=%s\n' "$SMB_PASS"
  [[ -n "$SMB_DOMAIN" ]] && printf 'domain=%s\n' "$SMB_DOMAIN"
} > "$CRED"
chmod 600 "$CRED"

SERVICE_USER=serveroficina
SERVICE_GROUP=serveroficina
UID_NUM=$(id -u "$SERVICE_USER")
GID_NUM=$(getent group "$SERVICE_GROUP" | cut -d: -f3)
OPTS="credentials=$CRED,iocharset=utf8,uid=$UID_NUM,gid=$GID_NUM,file_mode=0660,dir_mode=0770,nofail,_netdev,x-systemd.automount,x-systemd.idle-timeout=600"
LINE="$REMOTE $MOUNT_POINT cifs $OPTS 0 0"
TMP=$(mktemp)
grep -vF " $MOUNT_POINT cifs " /etc/fstab > "$TMP" || true
printf '%s\n' "$LINE" >> "$TMP"
cat "$TMP" > /etc/fstab
rm -f "$TMP"
systemctl daemon-reload
mount "$MOUNT_POINT" || true
if mountpoint -q "$MOUNT_POINT"; then
  echo "SMB_MOUNT_OK: $MOUNT_POINT"
else
  echo "SMB_MOUNT_PENDING/ERROR: revise red, credenciales y 'journalctl -xe'" >&2
  exit 4
fi
cat <<EOF
Configure ahora en Server Oficina > Evidencias > Repositorios:
  código: $CODE
  tipo: SMB
  mount_point: $MOUNT_POINT
  canonical_uri: $REMOTE
Las credenciales quedaron root-only en $CRED y NO se guardan en PostgreSQL.
EOF
