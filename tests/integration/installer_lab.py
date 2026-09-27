#!/usr/bin/env python3
from __future__ import annotations

"""Laboratorio del instalador real (``scripts/install-tablet.sh``) sin la Latitude.

El script de producción se ejecuta **sin modificar** dentro de un namespace de
montaje privado donde ``/opt/server-oficina``, ``/srv/server-oficina``,
``/etc/server-oficina`` y ``/etc/systemd/system`` son directorios temporales.
Sólo se sustituyen por stubs los comandos que no existen fuera del hardware:
``docker``, ``systemctl``, ``journalctl``, ``curl`` (health), ``apt-get``,
``ufw``, ``sleep`` y ``date`` (para forzar una colisión de release). ``rsync``,
``install``, ``useradd``, ``runuser``, el venv, ``pip`` y ``verify-package.sh``
son reales.

NO sustituye al gate físico: no hay systemd, PostgreSQL ni hardware reales.

Requiere root (o sudo) y ``unshare``. Uso:

    sudo -E LAB_ROOT=/tmp/installer-lab python3 tests/integration/installer_lab.py

Resultado en ``$LAB_ROOT/evidence.json``; imprime ``INSTALLER_LAB_OK``.
"""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LAB = Path(os.environ.get("LAB_ROOT", REPO / "runtime" / "installer-lab")).resolve()
BIN = LAB / "bin"
STATE = LAB / "state"
NS = {  # ruta real en el namespace -> directorio del laboratorio
    "/opt/server-oficina": LAB / "opt",
    "/srv/server-oficina": LAB / "srv",
    "/etc/server-oficina": LAB / "etc-so",
    "/etc/systemd/system": LAB / "etc-systemd",
    # Estado del reconciliador LAN y dispatcher de NetworkManager: nada fuera del sandbox.
    "/var/lib/server-oficina": LAB / "var-lib",
    "/etc/NetworkManager/dispatcher.d": LAB / "nm-dispatcher",
}
EVIDENCE: dict = {"scenarios": []}

UFW_STUB = r"""
exec python3 - "$@" <<'STUB'
import json, os, sys
db = os.path.join(os.environ["LAB_STATE"], "ufw.json")
state = json.load(open(db)) if os.path.exists(db) else {"rules": []}
active = os.environ.get("LAB_UFW", "inactive") == "active"
args = sys.argv[1:]
def save(): json.dump(state, open(db, "w"))
if args[:1] == ["status"]:
    print("Status: active" if active else "Status: inactive")
    if args[1:] == ["verbose"] and active:
        print(f"Default: {os.environ.get('LAB_UFW_DEFAULT', 'deny')} (incoming), allow (outgoing), disabled (routed)")
    if args[1:] == ["numbered"]:
        for i, r in enumerate(state["rules"], 1):
            a = r.get("args")
            to, frm = (f"{a[8]}/{a[10]} on {a[2]}", a[4]) if a else r["spec"].split(" ALLOW IN ")
            print(f"[{i:2d}] {to:<26} ALLOW IN    {frm:<26} # {r['comment']}")
elif args[:2] == ["--force", "delete"]:
    del state["rules"][int(args[2]) - 1]; save()
elif args[:1] == ["allow"]:
    if os.environ.get("LAB_UFW_FAIL_ALLOW") == "1":
        print("ERROR: fallo simulado del reconciliador", file=sys.stderr); sys.exit(1)
    rule_args, comment = args[1:args.index("comment")], args[args.index("comment") + 1]
    state["rules"].append({"spec": " ".join(rule_args), "args": rule_args, "comment": comment}); save()
else:
    sys.exit(2)
STUB
"""

IP_STUB = r"""
exec python3 - "$@" <<'STUB'
import json, os, sys
ifaces = json.load(open(os.path.join(os.environ["LAB_STATE"], "net.json")))["ifaces"]
args = sys.argv[1:]
if "neigh" in args:
    gw, dev = args[args.index("show") + 1], args[args.index("dev") + 1]
    for i in ifaces:
        if i["name"] == dev and i["gw"] == gw:
            print(f"{gw} lladdr {i['gw_mac']} REACHABLE")
elif "addr" in args:
    for idx, i in enumerate(ifaces, 2):
        print(f"{idx}: {i['name']}    inet {i['ip']} brd 0.0.0.0 scope global dynamic {i['name']}")
elif "default" in args:
    for i in ifaces:
        print(f"default via {i['gw']} dev {i['name']} proto dhcp metric {100 if i['kind'] == 'wired' else 600}")
STUB
"""

STUBS = {
    "apt-get": "exit 0\n",
    "journalctl": "exit 0\n",
    "sleep": "exit 0\n",
    "ping": "exit 0\n",
    # NetworkManager ausente: el reconciliador usa la huella sin perfil (gateway + medio).
    "nmcli": 'echo "Error: NetworkManager is not running." >&2; exit 8\n',
    # UFW con estado: LAB_UFW=active|inactive, LAB_UFW_DEFAULT=deny|allow, LAB_UFW_FAIL_ALLOW=1.
    "ufw": UFW_STUB,
    "ip": IP_STUB,
    "iw": (
        'python3 -c \'import json, os, sys; n = json.load(open(os.environ["LAB_STATE"] + "/net.json")); '
        'i = [i for i in n["ifaces"] if i["name"] == sys.argv[1]]; '
        'print("SSID: " + i[0]["ssid"] if i and i[0].get("ssid") else "Not connected.")\' "$2"\n'
    ),
    "date": (
        'if [[ "${1:-}" == "+%Y%m%d-%H%M%S" && -n "${LAB_STAMP:-}" ]]; then echo "$LAB_STAMP"; exit 0; fi\n'
        'exec /bin/date "$@"\n'
    ),
    "docker": r'''
case "$*" in
  "compose version") exit 0 ;;
  compose*"up -d postgres") touch "$LAB_STATE/postgres.up"; exit 0 ;;
  inspect\ -f*) echo healthy ;;
  "inspect server-oficina-postgres") exit 0 ;;
  *pg_dump*) printf 'PGDMP-installer-lab %s\n' "$(date +%s%N)" ;;
  *pg_isready*) exit 0 ;;
  *pg_restore*) cat > /dev/null; echo restored >> "$LAB_STATE/pg_restore.log"; exit 0 ;;
  # psql mínimo para restore.sh (la semántica real de PostgreSQL la cubre restore_lab.py).
  *psql*"datname = 'server_oficina'"*) echo 1 ;;
  *psql*"FROM pg_database"*) exit 0 ;;
  *psql*"FROM pg_tables"*) echo 3 ;;
  *psql*) echo "psql $*" >> "$LAB_STATE/psql.log"; echo 1 ;;
  logs*) exit 0 ;;
  *) echo "docker stub: $*" >&2; exit 0 ;;
esac
''',
    "curl": r'''
current=$(readlink -f /opt/server-oficina/current 2>/dev/null || true)
if [[ "${LAB_BREAK_HEALTH:-0}" == 1 && "$current" != "${LAB_GOOD_CURRENT:-}" ]]; then exit 7; fi
echo '{"status":"ok","lab":true}'
''',
    "systemctl": r'''
echo "systemctl $*" >> "$LAB_STATE/systemctl.log"
now=0; [[ "${1:-}" == "enable" || "${1:-}" == "disable" ]] && [[ "${2:-}" == "--now" ]] && now=1
current=$(readlink -f /opt/server-oficina/current 2>/dev/null || true)
broken=0
[[ "${LAB_BREAK_WORKER:-0}" == 1 && "$current" != "${LAB_GOOD_CURRENT:-}" ]] && broken=1
start() {
  if [[ "$1" == server-oficina-local-cloud && $broken == 1 ]]; then echo activating > "$LAB_STATE/$1.active"
  else echo active > "$LAB_STATE/$1.active"; fi
}
case "${1:-}" in
  daemon-reload|status|cat) exit 0 ;;
  enable) shift; [[ "${1:-}" == --now ]] && shift; for u in "$@"; do echo enabled > "$LAB_STATE/$u.enabled"; [[ $now == 1 ]] && start "$u"; done; exit 0 ;;
  disable) shift; [[ "${1:-}" == --now ]] && shift; for u in "$@"; do rm -f "$LAB_STATE/$u.enabled"; [[ $now == 1 ]] && echo inactive > "$LAB_STATE/$u.active"; done; exit 0 ;;
  restart|start) start "$2"; exit 0 ;;
  try-restart) u="${2%.service}"; [[ "$(cat "$LAB_STATE/$u.active" 2>/dev/null)" == active ]] && start "$u"; exit 0 ;;
  is-enabled) if [[ -f "$LAB_STATE/$2.enabled" ]]; then echo enabled; exit 0; fi; echo disabled; exit 1 ;;
  is-active) u="${!#}"; s=$(cat "$LAB_STATE/$u.active" 2>/dev/null || echo inactive); [[ "$2" == --quiet ]] || echo "$s"; [[ $s == active ]] ;;
  show)
    unit="${!#}"; f="$LAB_STATE/$unit.restarts"; n=$(cat "$f" 2>/dev/null || echo 0)
    if [[ "$unit" == server-oficina-local-cloud && $broken == 1 ]]; then n=$((n+1)); echo $n > "$f"; fi
    echo "$n"; exit 0 ;;
  *) exit 0 ;;
esac
''',
}


def sh(*args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs)


def lab_path(ns_path: str) -> Path:
    for prefix, target in NS.items():
        if ns_path == prefix or ns_path.startswith(prefix + "/"):
            return target / ns_path[len(prefix):].lstrip("/")
    raise ValueError(ns_path)


def current_release() -> str | None:
    link = NS["/opt/server-oficina"] / "current"
    return os.readlink(link) if link.is_symlink() else None


def service_state(unit: str) -> dict:
    return {
        "enabled": (STATE / f"{unit}.enabled").exists(),
        "active": (STATE / f"{unit}.active").read_text().strip() if (STATE / f"{unit}.active").exists() else "inactive",
    }


def prepare():
    if LAB.exists():
        shutil.rmtree(LAB)
    for path in [BIN, STATE, *NS.values()]:
        path.mkdir(parents=True)
    for name, body in STUBS.items():
        target = BIN / name
        target.write_text("#!/usr/bin/env bash\n" + body)
        target.chmod(0o755)
    # Candidata: archivos versionados del árbol actual, con su propio git y MANIFEST.
    src = LAB / "src"
    src.mkdir()
    files = sh("git", "-C", str(REPO), "ls-files", "-z").stdout.split("\0")
    for rel in filter(None, files):
        source = REPO / rel
        if source.is_file():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, src / rel)
    sh("bash", str(src / "scripts" / "generate-manifest.sh"))
    git = ["git", "-C", str(src), "-c", "user.email=lab@lab", "-c", "user.name=lab"]
    sh(*git, "init", "-q")
    sh(*git, "add", "-A")
    sh(*git, "commit", "-qm", "candidata laboratorio")
    # Dueño no root, como un checkout de adminoficina.
    subprocess.run(["chown", "-R", "1000:1000", str(src)], check=False)
    return src


def run_installer(src: Path, name: str, *args: str, **env_extra) -> subprocess.CompletedProcess:
    return run_in_ns(f'exec "{src}/scripts/install-tablet.sh" {" ".join(args)}', name, **env_extra)


def run_in_ns(command: str, name: str, *, pre: str = "", **env_extra) -> subprocess.CompletedProcess:
    mounts = "\n".join(f'mkdir -p "{ns}" && mount --bind "{real}" "{ns}"' for ns, real in NS.items())
    script = f"set -e\n{mounts}\n{pre}\n{command}\n"
    env = {k: v for k, v in os.environ.items() if k not in {"SUDO_USER", "SUDO_UID", "SUDO_GID"}}
    env.update({"PATH": f"{BIN}:{os.environ['PATH']}", "LAB_STATE": str(STATE),
                # Interfaces simuladas (Ethernet/Wi-Fi) para el reconciliador LAN.
                "SO_LAN_FIREWALL_SYSFS": str(LAB / "sysfs"), **env_extra})
    result = subprocess.run(
        ["unshare", "--mount", "--propagation", "private", "bash", "-c", script],
        env=env, text=True, capture_output=True, timeout=1800,
    )
    (LAB / f"{name}.log").write_text(result.stdout + "\n--- stderr ---\n" + result.stderr)
    return result


def check(name: str, condition: bool, detail: str = ""):
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def record(name: str, result: subprocess.CompletedProcess, **facts):
    entry = {"escenario": name, "exit": result.returncode, **facts}
    EVIDENCE["scenarios"].append(entry)
    print(f"INSTALLER_LAB_STEP {json.dumps(entry, ensure_ascii=False)}", flush=True)


def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(p for p in path.rglob("*") if p.is_file() and ".venv" not in p.parts):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(item.read_bytes())
    return digest.hexdigest()


def mode(path: Path) -> str:
    st = path.stat()
    return f"{st.st_uid}:{st.st_gid}:{stat.S_IMODE(st.st_mode):04o}"


def env_host() -> str:
    text = (NS["/etc/server-oficina"] / "server-oficina.env").read_text()
    return next(l.split("=", 1)[1] for l in text.splitlines() if l.startswith("SERVER_OFICINA_HOST="))


def managed_rules() -> list[str]:
    db = STATE / "ufw.json"
    rules = json.loads(db.read_text())["rules"] if db.exists() else []
    return [r["spec"] for r in rules if r["comment"] == "server-oficina-lan"]


ETH_LAN = {"name": "eth0", "kind": "wired", "gw": "192.168.48.1", "ip": "192.168.48.109/24",
           "gw_mac": "aa:bb:cc:00:00:01"}
WIFI_LAN = {"name": "wlan0", "kind": "wifi", "gw": "10.20.0.1", "ip": "10.20.0.57/24",
            "gw_mac": "aa:bb:cc:00:00:02", "ssid": "Oficina-B"}


def set_network(*ifaces: dict, **values):
    """LAN activas de la Latitude simulada. Sin argumentos: sólo eth0 (con ``values`` aplicados)."""
    ifaces = ifaces or ({**ETH_LAN, **values},)
    sysfs = LAB / "sysfs"
    shutil.rmtree(sysfs, ignore_errors=True)
    for i in ifaces:
        (sysfs / i["name"] / "device").mkdir(parents=True)
        (sysfs / i["name"] / "type").write_text("1\n")
        (sysfs / i["name"] / "operstate").write_text("up\n")
        if i["kind"] == "wifi":
            (sysfs / i["name"] / "wireless").mkdir()
    (STATE / "net.json").write_text(json.dumps({"ifaces": list(ifaces)}))


def lan_fail_closed(src: Path) -> str:
    """Publicación LAN fail-closed: sin demostración, la API queda en 127.0.0.1 y no se declara sana."""
    ssh = {"spec": "22/tcp ALLOW IN Anywhere", "comment": "ssh"}
    legacy = {"spec": "8080/tcp on eth0 ALLOW IN 192.168.48.0/24", "comment": "Server Oficina LAN"}
    (STATE / "ufw.json").write_text(json.dumps({"rules": [ssh, legacy]}))
    set_network()
    configure = "exec /opt/server-oficina/current/scripts/configurar-acceso-lan.sh"

    r = run_installer(src, "s2a_lan_sin_red_confiable", LAB_UFW="active")
    rules = json.loads((STATE / "ufw.json").read_text())["rules"]
    check("s2a", r.returncode == 10 and "LAN_NO_PUBLICADA" in r.stderr and "INSTALACION_SOLO_LOCAL" in r.stderr,
          f"exit={r.returncode} {r.stderr[-800:]}")
    check("s2a loopback", env_host() == "127.0.0.1", env_host())
    check("s2a reglas", managed_rules() == [] and ssh in rules and legacy not in rules, str(rules))
    record("lan_sin_red_confiable_no_declara_sana", r, host=env_host(), reglas_lan=managed_rules(),
           ssh_intacta=ssh in rules, regla_legado_subred_eliminada=legacy not in rules)

    r = run_installer(src, "s2b_lan_reconciliador_falla", "--confiar-red-actual",
                      LAB_UFW="active", LAB_UFW_FAIL_ALLOW="1")
    check("s2b", r.returncode == 10 and "LAN_NO_PUBLICADA" in r.stderr, f"exit={r.returncode} {r.stderr[-800:]}")
    check("s2b loopback", env_host() == "127.0.0.1" and managed_rules() == [], env_host())
    record("lan_reconciliador_falla_api_solo_loopback", r, host=env_host(), reglas_lan=managed_rules())

    r = run_installer(src, "s2c_lan_publicada", "--confiar-red-actual", LAB_UFW="active")
    check("s2c", r.returncode == 0 and "LAN_PUBLICADA" in r.stdout, f"exit={r.returncode} {r.stderr[-800:]}")
    expected = ["in on eth0 from 192.168.48.0/24 to any port 8080 proto tcp"]
    check("s2c publicada", env_host() == "0.0.0.0" and managed_rules() == expected, f"{env_host()} {managed_rules()}")
    check("s2c ssh", ssh in json.loads((STATE / "ufw.json").read_text())["rules"])
    record("lan_publicada_con_red_confiable", r, host=env_host(), reglas_lan=managed_rules())

    r = run_in_ns(configure, "s2d_ufw_politica_allow", LAB_UFW="active", LAB_UFW_DEFAULT="allow")
    check("s2d", r.returncode == 10 and env_host() == "127.0.0.1", f"exit={r.returncode} host={env_host()}")
    record("ufw_politica_allow_despublica", r, host=env_host())

    run_in_ns(configure, "s2e_republicar", LAB_UFW="active")
    check("s2e republicada", env_host() == "0.0.0.0" and managed_rules() == expected, env_host())
    set_network(gw_mac="aa:bb:cc:99:99:99")  # misma eth0, otra LAN
    r = run_in_ns(configure, "s2e_misma_interfaz_otra_red", LAB_UFW="active")
    check("s2e", r.returncode == 10 and env_host() == "127.0.0.1" and managed_rules() == [],
          f"exit={r.returncode} host={env_host()} {managed_rules()}")
    record("misma_interfaz_otra_red_despublica", r, host=env_host(), reglas_lan=managed_rules())
    return current_release()


def multi_lan(src: Path):
    """Ethernet + Wi-Fi activas a la vez: cada LAN se confía y se publica por separado."""
    configure = "exec /opt/server-oficina/current/scripts/configurar-acceso-lan.sh"
    reconcile = "exec python3 /opt/server-oficina/current/scripts/lan_firewall.py apply --sync-api"
    set_network(ETH_LAN, WIFI_LAN)
    both = ["in on eth0 from 192.168.48.0/24 to any port 8080 proto tcp",
            "in on wlan0 from 10.20.0.0/24 to any port 8080 proto tcp"]

    r = run_in_ns(f"{configure} --confiar-red-actual", "s2f_dos_lan_confiar_ambiguo", LAB_UFW="active")
    check("s2f ambiguo", r.returncode == 10 and "varias LAN activas" in r.stderr and env_host() == "127.0.0.1",
          f"exit={r.returncode} {r.stderr[-600:]}")
    check("s2f sin confiar la Wi-Fi", not any("wlan0" in rule for rule in managed_rules()), str(managed_rules()))
    record("dos_lan_confiar_red_actual_es_ambiguo", r, host=env_host(), reglas_lan=managed_rules())

    r = run_in_ns(f"{configure} --confiar-interfaz eth0 --confiar-interfaz wlan0", "s2f_dos_lan_publicadas",
                  LAB_UFW="active")
    check("s2f publicadas", r.returncode == 0 and env_host() == "0.0.0.0" and sorted(managed_rules()) == both,
          f"exit={r.returncode} host={env_host()} {managed_rules()} {r.stderr[-600:]}")
    check("s2f URLs por LAN", "http://192.168.48.109:8080" in r.stdout and "http://10.20.0.57:8080" in r.stdout,
          r.stdout[-800:])
    record("ethernet_y_wifi_publicadas", r, host=env_host(), reglas_lan=managed_rules())

    (STATE / "systemctl.log").write_text("")
    set_network(ETH_LAN)  # cae la Wi-Fi
    r = run_in_ns(reconcile, "s2g_cae_wifi", LAB_UFW="active")
    log = (STATE / "systemctl.log").read_text()
    check("s2g", r.returncode == 0 and env_host() == "0.0.0.0" and managed_rules() == [both[0]]
          and "try-restart" not in log, f"host={env_host()} {managed_rules()} {log}")
    record("cae_wifi_ethernet_sigue_sin_reiniciar_api", r, host=env_host(), reglas_lan=managed_rules())

    set_network(WIFI_LAN)  # vuelve la Wi-Fi y cae el cable
    run_in_ns(reconcile, "s2g_cae_ethernet", LAB_UFW="active")
    check("s2g cable", env_host() == "0.0.0.0" and managed_rules() == [both[1]], str(managed_rules()))

    set_network(dict(WIFI_LAN, gw_mac="aa:bb:cc:99:99:99"))  # sólo queda una LAN desconocida
    r = run_in_ns(reconcile, "s2h_ninguna_lan_confiable", LAB_UFW="active")
    log = (STATE / "systemctl.log").read_text()
    check("s2h", env_host() == "127.0.0.1" and managed_rules() == [] and "try-restart server-oficina" in log,
          f"host={env_host()} {managed_rules()} {log}")
    record("ninguna_lan_confiable_api_loopback", r, host=env_host(), reglas_lan=managed_rules())

    set_network(ETH_LAN, WIFI_LAN)  # vuelven ambas
    r = run_in_ns(reconcile, "s2h_vuelven_ambas", LAB_UFW="active")
    check("s2h vuelven", env_host() == "0.0.0.0" and sorted(managed_rules()) == both, str(managed_rules()))
    record("vuelven_ambas_lan", r, host=env_host(), reglas_lan=sorted(managed_rules()))


def reset_state():
    for path in [STATE, *NS.values()]:
        shutil.rmtree(path)
        path.mkdir(parents=True)


def backup_and_restore(release: str):
    """Backup diario: inventario de versions/, identidad Syncthing, réplica externa fail-closed."""
    link = NS["/opt/server-oficina"] / "current"
    link.unlink()
    link.symlink_to(release)
    srv = NS["/srv/server-oficina"]
    for payload in (b"objeto-uno", b"objeto-dos"):
        digest = hashlib.sha256(payload).hexdigest()
        target = srv / "versions" / "sha256" / digest[:2] / digest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    identity = srv / "syncthing" / ".local" / "state" / "syncthing"
    identity.mkdir(parents=True)
    for name in ("cert.pem", "key.pem", "config.xml"):
        (identity / name).write_text(f"lab {name}\n")
    backup = "exec /opt/server-oficina/current/scripts/backup.sh"

    same_second = "20260927-120000"  # tres respaldos en el mismo segundo (manual + timer)
    r = run_in_ns(backup, "s7_backup_sin_replica", LAB_STAMP=same_second)
    # backup.sh imprime su directorio: no se deduce por nombre (dos respaldos en
    # el mismo segundo reciben sufijo único y el orden alfabético no sirve).
    daily = lab_path(r.stdout.strip().splitlines()[-1])
    info = (daily / "BACKUP_INFO").read_text()
    sums = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=daily, capture_output=True, text=True)
    key_mode = stat.S_IMODE((daily / "syncthing-hub-identity.tar.gz").stat().st_mode)
    check("s7", r.returncode == 0 and "versions_replica_externa=NO_CONFIGURADA" in info
          and "versions_objetos=2" in info and sums.returncode == 0 and key_mode == 0o600,
          r.stderr[-800:] + info + sums.stdout)
    check("s7 aviso", "sin réplica externa" in r.stderr)
    record("backup_diario_sin_replica_externa", r, backup=daily.name, sha_ok=True,
           identidad_syncthing_modo=f"{key_mode:04o}", inventario_objetos=2)

    (NS["/etc/server-oficina"] / "backup.env").write_text("BACKUP_VERSIONS_DEST=/mnt/so-respaldo/versions\n")
    r = run_in_ns(backup, "s8_replica_no_montada", pre="mkdir -p /mnt/so-respaldo", LAB_STAMP=same_second)
    failed_dir = lab_path(r.stdout.strip().splitlines()[-1])
    check("s8 fail-closed", r.returncode == 3 and "no está montado" in r.stderr, r.stderr[-500:])
    record("replica_externa_no_montada_fail_closed", r)

    replica = LAB / "replica"
    replica.mkdir()
    r = run_in_ns(backup, "s9_replica_ok",
                  pre=f'mkdir -p /mnt/so-respaldo && mount -t tmpfs tmpfs /mnt/so-respaldo && '
                      f'trap "cp -a /mnt/so-respaldo/. {replica}/" EXIT', LAB_STAMP=same_second)
    check("s9", r.returncode == 0, r.stderr[-800:])
    first_daily = daily
    daily = lab_path(r.stdout.strip().splitlines()[-1])
    info = (daily / "BACKUP_INFO").read_text()
    check("s9 directorios únicos", len({first_daily, failed_dir, daily}) == 3,
          f"{first_daily.name} {failed_dir.name} {daily.name}")
    check("s9 replica", "versions_replica_externa=OK:2_nuevos" in info, info)
    record("replica_externa_versions_verificada", r, info=info.strip().splitlines())

    (STATE / "server-oficina-local-cloud.active").write_text("active\n")
    r = run_in_ns(f'exec /opt/server-oficina/current/scripts/restore.sh "/srv/server-oficina/backups/server-oficina/{daily.name}"',
                  "s10_restore")
    log = (STATE / "systemctl.log").read_text().splitlines()
    stop_observer = max(i for i, l in enumerate(log) if l == "systemctl stop server-oficina-local-cloud")
    start_observer = max(i for i, l in enumerate(log) if l == "systemctl start server-oficina-local-cloud")
    check("s10", r.returncode == 0 and (STATE / "pg_restore.log").exists(), r.stderr[-800:])
    check("s10 observador", stop_observer < start_observer)
    check("s10 identidad no aplicada", "NO se aplica automáticamente" in r.stdout)
    check("s10 RESTORE_OK", "RESTORE_OK" in r.stdout, r.stdout[-400:])
    psql_log = (STATE / "psql.log").read_text()
    check("s10 intercambio atómico", "_pre_restore_" in psql_log and "BEGIN; ALTER DATABASE" in psql_log, psql_log)
    record("restore_con_observador", r, observador_detenido_y_reiniciado=True,
           verificacion_historial="AVISO sin PostgreSQL en laboratorio" if "AVISO" in r.stderr else "ejecutada")


def main() -> int:
    if os.geteuid() != 0:
        print("installer_lab requiere root (sudo -E)", file=sys.stderr)
        return 2
    src = prepare()

    # 0 · primera instalación con health roto: sin release previa no hay rollback
    #     posible, pero `current` jamás puede quedar apuntándose a sí mismo.
    r = run_installer(src, "s0_primera_rota", LAB_BREAK_HEALTH="1", LAB_GOOD_CURRENT="ninguna")
    link = NS["/opt/server-oficina"] / "current"
    target = current_release()
    check("s0", r.returncode == 5, r.stderr[-1500:])
    check("s0 sin bucle", target is not None and target != "/opt/server-oficina/current"
          and lab_path(target).is_dir(), str(target))
    check("s0 previa", "Release activa previa: NINGUNA" in r.stdout, r.stdout[:300])
    check("s0 observador no habilitado", not service_state("server-oficina-local-cloud")["enabled"])
    record("primera_instalacion_health_fail", r, current=target, symlink_valido=lab_path(target).is_dir())
    reset_state()

    # 1 · instalación limpia
    r = run_installer(src, "s1_limpia")
    check("s1", r.returncode == 0, r.stderr[-2000:])
    first = current_release()
    rel1 = lab_path(first)
    env_text = (NS["/etc/server-oficina"] / "server-oficina.env").read_text()
    world_or_group_writable = [
        str(p) for p in rel1.rglob("*")
        if ".venv" not in p.parts and not p.is_symlink() and stat.S_IMODE(p.stat().st_mode) & 0o022
    ]
    code_owners = {p.stat().st_uid for p in rel1.rglob("*") if ".venv" not in p.parts and not p.is_symlink()}
    backups = sorted((NS["/srv/server-oficina"] / "backups" / "server-oficina").glob("pre-upgrade-*"))
    sums_ok = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=backups[-1], capture_output=True).returncode == 0
    check("s1 current", first.startswith("/opt/server-oficina/releases/") and "+" in first, first)
    check("s1 dueño root", code_owners == {0}, str(code_owners))
    check("s1 sin escritura grupo/otros", not world_or_group_writable, str(world_or_group_writable[:5]))
    check("s1 env", "SERVER_OFICINA_SYNC_ROOT=/srv/server-oficina/files" in env_text
          and "SERVER_OFICINA_VERSIONS_ROOT=/srv/server-oficina/versions" in env_text, env_text)
    check("s1 unidades", all((NS["/etc/systemd/system"] / u).is_file() for u in (
        "server-oficina.service", "server-oficina-local-cloud.service",
        "server-oficina-backup.service", "server-oficina-backup.timer")))
    check("s1 observador", service_state("server-oficina-local-cloud") == {"enabled": True, "active": "active"})
    check("s1 backup", sums_ok and "LOCAL_CLOUD_OK" in r.stdout and "PRE_UPGRADE_BACKUP_OK" in r.stdout)
    record("instalacion_limpia", r, release=first,
           files=mode(NS["/srv/server-oficina"] / "files"), versions=mode(NS["/srv/server-oficina"] / "versions"),
           codigo_dueno_root=True, backup_sha_ok=sums_ok, observador=service_state("server-oficina-local-cloud"))

    # 2 · reinstalar la misma VERSION: directorio nuevo, previa intacta, env del operador conservado
    env_file = NS["/etc/server-oficina"] / "server-oficina.env"
    env_file.write_text(env_file.read_text() + "SERVER_OFICINA_SYNCTHING_API_KEY=clave-del-operador\n")
    before = tree_digest(rel1)
    r = run_installer(src, "s2_reinstalar")
    check("s2", r.returncode == 0, r.stderr[-2000:])
    second = current_release()
    info = (lab_path(second) / "RELEASE_INFO").read_text()
    check("s2 release nueva", second != first)
    check("s2 previa intacta", tree_digest(rel1) == before)
    check("s2 RELEASE_INFO", f"previous_release={first}" in info, info)
    check("s2 env operador", "SERVER_OFICINA_SYNCTHING_API_KEY=clave-del-operador" in env_file.read_text())
    record("reinstalar_misma_version", r, release=second, previa=first, previa_intacta=True,
           env_operador_conservado=True)

    second = lan_fail_closed(src)
    multi_lan(src)

    # 3 · colisión forzada: mismo instante => directorio existente => no se toca nada
    stamp = second.rsplit("+", 1)[1].split(".", 1)[0]
    r = run_installer(src, "s3_colision", LAB_STAMP=stamp)
    check("s3", r.returncode == 6 and "RELEASE_COLLISION" in r.stderr, r.stderr[-500:])
    check("s3 current intacto", current_release() == second)
    record("colision_de_release", r, current=current_release())

    # 4 · health falla => rollback a la release previa CON su configuración previa
    env_file = NS["/etc/server-oficina"] / "server-oficina.env"
    # Release previa publicada en LAN (0.0.0.0): la candidata escribe 127.0.0.1;
    # tras el rollback debe volver exactamente la configuración previa.
    env_file.write_text(env_file.read_text().replace("SERVER_OFICINA_HOST=127.0.0.1", "SERVER_OFICINA_HOST=0.0.0.0"))
    before_env = env_file.read_text()
    assert "SERVER_OFICINA_HOST=0.0.0.0" in before_env
    r = run_installer(src, "s4_health", LAB_BREAK_HEALTH="1", LAB_GOOD_CURRENT=second)
    check("s4", r.returncode == 5 and "ROLLBACK_RELEASE_OK" in r.stderr, r.stderr[-1500:])
    check("s4 current", current_release() == second)
    check("s4 env previo restaurado", env_file.read_text() == before_env)
    check("s4 observador intacto", service_state("server-oficina-local-cloud")["enabled"])
    record("health_fail_rollback", r, current=current_release(), env_previo_restaurado=True,
           observador=service_state("server-oficina-local-cloud"))

    # 5 · observador en bucle de reinicios => rollback; la previa tenía observador activo
    r = run_installer(src, "s5_observador", LAB_BREAK_WORKER="1", LAB_GOOD_CURRENT=second)
    check("s5", r.returncode == 7 and "LOCAL_CLOUD_FAIL" in r.stderr and "ROLLBACK_RELEASE_OK" in r.stderr,
          r.stderr[-1500:])
    check("s5 current", current_release() == second)
    check("s5 observador sigue habilitado", service_state("server-oficina-local-cloud")["enabled"])
    record("observador_falla_rollback", r, current=current_release())

    # 6 · actualización desde una release legado (sin observador) que falla => se deshabilita
    legacy_ns = "/opt/server-oficina/releases/0.1.0-alpha.2"
    legacy = lab_path(legacy_ns)
    (legacy / "app").mkdir(parents=True)
    (legacy / "VERSION").write_text("0.1.0-alpha.2\n")
    link = NS["/opt/server-oficina"] / "current"
    link.unlink()
    link.symlink_to(legacy_ns)
    (STATE / "server-oficina-local-cloud.enabled").unlink()
    (STATE / "server-oficina-local-cloud.active").write_text("inactive\n")
    r = run_installer(src, "s6_legado", LAB_BREAK_WORKER="1", LAB_GOOD_CURRENT=legacy_ns)
    check("s6", r.returncode == 7, r.stderr[-1500:])
    check("s6 current legado", current_release() == legacy_ns)
    check("s6 observador deshabilitado", not service_state("server-oficina-local-cloud")["enabled"])
    record("rollback_a_legado_sin_observador", r, current=current_release(),
           observador=service_state("server-oficina-local-cloud"))

    backup_and_restore(second)
    releases = sorted(p.name for p in (NS["/opt/server-oficina"] / "releases").iterdir())
    EVIDENCE["releases_conservadas"] = releases
    EVIDENCE["result"] = "INSTALLER_LAB_OK"
    (LAB / "evidence.json").write_text(json.dumps(EVIDENCE, indent=2, ensure_ascii=False))
    print("INSTALLER_LAB_OK", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - toda falla del laboratorio queda como evidencia
        EVIDENCE["result"] = f"FAIL: {exc.__class__.__name__}: {exc}"
        (LAB / "evidence.json").write_text(json.dumps(EVIDENCE, indent=2, ensure_ascii=False))
        print(f"INSTALLER_LAB_FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
