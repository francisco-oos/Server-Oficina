#!/usr/bin/env bash
set -euo pipefail
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Ejecute con sudo/root" >&2; exit 1; }
apt-get update >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y samba >/dev/null
LOGIN_USER=${SUDO_USER:-adminoficina}
read -rp "Nombre del recurso Windows [Evidencias]: " SHARE
SHARE=${SHARE:-Evidencias}
read -rp "Carpeta local [/srv/server-oficina/data/app/inbox]: " PATH_LOCAL
PATH_LOCAL=${PATH_LOCAL:-/srv/server-oficina/data/app/inbox}
mkdir -p "$PATH_LOCAL"
chown "$LOGIN_USER":serveroficina "$PATH_LOCAL"
chmod 2770 "$PATH_LOCAL"

CONF=/etc/samba/smb.conf
BEGIN="# BEGIN SERVER_OFICINA_EVIDENCE_INBOX"
END="# END SERVER_OFICINA_EVIDENCE_INBOX"
python3 - "$CONF" "$BEGIN" "$END" "$SHARE" "$PATH_LOCAL" "$LOGIN_USER" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); begin,end,share,path,user=sys.argv[2:]
s=p.read_text() if p.exists() else "[global]\n   workgroup = WORKGROUP\n"
if begin in s and end in s:
    a=s.index(begin); b=s.index(end,a)+len(end); s=s[:a]+s[b:]
s=s.rstrip()+f"\n\n{begin}\n[{share}]\n   path = {path}\n   browseable = yes\n   read only = no\n   valid users = {user}\n   force group = serveroficina\n   create mask = 0660\n   directory mask = 2770\n{end}\n"
p.write_text(s)
PY

testparm -s >/dev/null
systemctl enable --now smbd
printf 'Configure la contraseña SMB para %s (puede ser distinta a Linux):\n' "$LOGIN_USER"
smbpasswd -a "$LOGIN_USER"
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q '^Status: active'; then
  IFACE=$(ip route show default | awk 'NR==1{print $5}')
  CIDR=$(ip -o -f inet addr show "$IFACE" | awk 'NR==1{print $4}')
  if [[ -n "${CIDR:-}" ]]; then ufw allow in on "$IFACE" from "$CIDR" to any app Samba >/dev/null || true; fi
fi
IP=$(hostname -I | awk '{print $1}')
echo "BANDEJA_SMB_OK: \\\\${IP:-server-oficina}\\$SHARE"
echo "Esta bandeja es opcional para recepción; el NAS externo sigue siendo configurable y preferido para evidencia pesada."
