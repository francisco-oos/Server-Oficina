#!/usr/bin/env python3
from __future__ import annotations

"""Laboratorio multi-LAN con red real: la Latitude en Ethernet y Wi-Fi a la vez.

Namespaces de red (requiere root):

    so-ml-pca ── so-ml-lana (switch+router 192.168.10.1) ── enp0s31f6 ┐
                                                                     so-ml-hub (Latitude)
    so-ml-pcb ── so-ml-lanb (switch+router 192.168.48.1) ── wlp2s0 ──┘

Real: iproute2, UFW (iptables del namespace del hub, /etc/ufw aislado), Avahi,
Syncthing 2.x y ``scripts/lan_firewall.py`` sin modificar. Simulado: que
``wlp2s0`` es Wi-Fi (un veth no es una radio: sysfs con ``wireless`` y un
``iw`` que informa el SSID), NetworkManager ausente y la API (un servidor HTTP
mínimo que escucha en ``SERVER_OFICINA_HOST``; ``systemctl try-restart`` lo
reinicia).

Comprueba: reglas UFW simultáneas por interfaz, HTTP desde cada LAN,
``server-oficina.local`` resuelto a la IP de la propia LAN, Syncthing conectado
por ambas LAN, caída y regreso independiente de cada interfaz, Ethernet en una
LAN desconocida, ninguna LAN → API sólo en loopback, y que la Latitude no
enruta entre LAN (con control positivo).

NO sustituye al gate físico (Wi-Fi real, NetworkManager real, Latitude).

    sudo -E SYNCTHING_BIN=/ruta/syncthing LAB_ROOT=/tmp/ml python3 tests/integration/multi_lan_lab.py
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LAB = Path(os.environ.get("LAB_ROOT", REPO / "runtime" / "multi-lan-lab")).resolve()
SYNCTHING = os.environ.get("SYNCTHING_BIN") or shutil.which("syncthing")
P = "so-ml-"
ETH, WIFI = "enp0s31f6", "wlp2s0"
HUB_A, HUB_B, PC_A, PC_B = "192.168.10.23", "192.168.48.109", "192.168.10.50", "192.168.48.60"
LAN_A, LAN_B = "192.168.10.0/24", "192.168.48.0/24"
API_KEY = "multi-lan-lab-key"
EVIDENCE: dict = {"fases": []}
PROCS: dict[str, subprocess.Popen] = {}


# ---------------------------------------------------------------- utilidades

def sh(*args: str, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=check, text=True, capture_output=True, **kwargs)


def ns(name: str, *args: str, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    return sh("ip", "netns", "exec", P + name, *args, check=check, **kwargs)


def hub_env() -> dict[str, str]:
    return {**os.environ, "PATH": f"{LAB / 'bin'}:{os.environ['PATH']}", "MLAB": str(LAB),
            "SO_LAN_FIREWALL_CONF": str(LAB / "etc-so" / "lan-firewall.json"),
            "SO_LAN_FIREWALL_STATE": str(LAB / "var" / "lan-firewall-state.json"),
            "SO_LAN_FIREWALL_LOCK": str(LAB / "lan-firewall.lock"),
            "SO_LAN_FIREWALL_SYSFS": str(LAB / "sysfs"),
            "SO_ENV_FILE": str(LAB / "etc-so" / "server-oficina.env"),
            "SO_AVAHI_CONF": str(LAB / "avahi-daemon.conf")}


def hub_script(command: str, *, avahi: bool = False) -> list[str]:
    """Comando en la Latitude: namespace de red del hub + /etc/ufw aislado + hostname server-oficina."""
    mounts = [f"mount --bind {LAB / 'etc-ufw'} /etc/ufw", f"mount --bind {LAB / 'default-ufw'} /etc/default/ufw"]
    if avahi:
        mounts += ["mkdir -p /run/avahi-daemon", f"mount --bind {LAB / 'avahi-run'} /run/avahi-daemon"]
    script = "set -e\n" + "\n".join(mounts) + "\nhostname server-oficina\n" + command + "\n"
    return ["ip", "netns", "exec", P + "hub", "unshare", "--mount", "--uts", "--propagation", "private",
            "bash", "-c", script]


def hub(command: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(hub_script(command), env=hub_env(), text=True, capture_output=True)
    if check and result.returncode != 0:
        raise AssertionError(f"hub: {command}\n{result.stdout[-1500:]}\n{result.stderr[-1500:]}")
    return result


def firewall(*args: str) -> tuple[int, dict | None, str]:
    """lan_firewall.py real dentro de la Latitude simulada."""
    result = hub(f"exec python3 {REPO / 'scripts' / 'lan_firewall.py'} {' '.join(args)}", check=False)
    match = re.search(r"^(LAN_FIREWALL|LAN_AUDIT) (.*)$", result.stdout, re.M)
    return result.returncode, json.loads(match.group(2)) if match else None, result.stderr


def check(name: str, condition: bool, detail: str = ""):
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def record(name: str, **facts):
    entry = {"fase": name, **facts}
    EVIDENCE["fases"].append(entry)
    print(f"MULTI_LAN_STEP {json.dumps(entry, ensure_ascii=False)}", flush=True)


def wait_until(label: str, predicate, timeout: float = 150.0, interval: float = 1.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except Exception as exc:  # noqa: BLE001 - se reintenta hasta el plazo
            last = exc
        time.sleep(interval)
    raise AssertionError(f"timeout esperando {label}: {last}")


# ---------------------------------------------------------------- red

def build_network():
    for name in ("hub", "lana", "lanb", "pca", "pcb"):
        sh("ip", "netns", "add", P + name)
        sh("ip", "-n", P + name, "link", "set", "lo", "up")
    for lan, gw in (("lana", "192.168.10.1/24"), ("lanb", "192.168.48.1/24")):
        sh("ip", "-n", P + lan, "link", "add", "br0", "type", "bridge")
        sh("ip", "-n", P + lan, "addr", "add", gw, "dev", "br0")
        sh("ip", "-n", P + lan, "link", "set", "br0", "up")
    # Latitude: una interfaz por LAN, con nombres predictivos como en Debian.
    sh("ip", "link", "add", ETH, "netns", P + "hub", "type", "veth", "peer", "name", "hub-a", "netns", P + "lana")
    sh("ip", "link", "add", WIFI, "netns", P + "hub", "type", "veth", "peer", "name", "hub-b", "netns", P + "lanb")
    sh("ip", "link", "add", "eth0", "netns", P + "pca", "type", "veth", "peer", "name", "pc-a", "netns", P + "lana")
    sh("ip", "link", "add", "eth0", "netns", P + "pcb", "type", "veth", "peer", "name", "pc-b", "netns", P + "lanb")
    for lan, ports in (("lana", ("hub-a", "pc-a")), ("lanb", ("hub-b", "pc-b"))):
        for port in ports:
            sh("ip", "-n", P + lan, "link", "set", port, "master", "br0", "up")
    for iface, address in ((ETH, f"{HUB_A}/24"), (WIFI, f"{HUB_B}/24")):
        sh("ip", "-n", P + "hub", "addr", "add", address, "dev", iface)
    for pc, address, gw in (("pca", f"{PC_A}/24", "192.168.10.1"), ("pcb", f"{PC_B}/24", "192.168.48.1")):
        sh("ip", "-n", P + pc, "addr", "add", address, "dev", "eth0")
        sh("ip", "-n", P + pc, "link", "set", "eth0", "up")
        sh("ip", "-n", P + pc, "route", "add", "default", "via", gw)
    link_up(ETH)
    link_up(WIFI)


def link_up(iface: str):
    """Como NetworkManager: enlace arriba y su ruta por defecto (Ethernet métrica 100, Wi-Fi 600)."""
    sh("ip", "-n", P + "hub", "link", "set", iface, "up")
    gw, metric = ("192.168.10.1", "100") if iface == ETH else ("192.168.48.1", "600")
    # La ruta de la subred vuelve con el enlace; hasta entonces el gateway no es alcanzable.
    wait_until(f"ruta por defecto en {iface}", lambda: sh(
        "ip", "-n", P + "hub", "route", "replace", "default", "via", gw, "dev", iface, "metric", metric,
        check=False).returncode == 0, 10, 0.2)


def link_down(iface: str):
    sh("ip", "-n", P + "hub", "link", "set", iface, "down")


def destroy_network():
    for name in ("hub", "lana", "lanb", "pca", "pcb"):
        subprocess.run(["ip", "netns", "del", P + name], capture_output=True)


# ---------------------------------------------------------------- Latitude simulada

STUB_SYSTEMCTL = r'''#!/usr/bin/env bash
echo "systemctl $*" >> "$MLAB/systemctl.log"
case "$1" in
  try-restart)
    if [[ "$2" == server-oficina.service && -f "$MLAB/api.pid" ]]; then
      kill "$(cat "$MLAB/api.pid")" 2>/dev/null || true
      for _ in $(seq 1 50); do kill -0 "$(cat "$MLAB/api.pid")" 2>/dev/null || break; sleep 0.1; done
      setsid -f python3 "$MLAB/api.py" >> "$MLAB/api.log" 2>&1 < /dev/null
    fi ;;
  is-active)
    if [[ "${!#}" == avahi-daemon ]]; then
      if kill -0 "$(cat "$MLAB/avahi-run/pid" 2>/dev/null)" 2>/dev/null; then echo active; else echo inactive; exit 3; fi
    fi ;;
esac
exit 0
'''

API = r'''import http.server, json, os
LAB = os.environ["MLAB"]
env = open(f"{LAB}/etc-so/server-oficina.env").read().splitlines()
host = [l.split("=", 1)[1].strip() for l in env if l.startswith("SERVER_OFICINA_HOST=")][-1]
class Health(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"status": "ok", "bind": host}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass
server = http.server.ThreadingHTTPServer((host, 8080), Health)
open(f"{LAB}/api.pid", "w").write(str(os.getpid()))
server.serve_forever()
'''

MDNS_QUERY = r'''import random, socket, struct, sys
name, target = sys.argv[1], sys.argv[2]  # target: 224.0.0.251 (multicast) o la IP del hub (unicast)
query = struct.pack("!HHHHHH", random.randint(1, 65535), 0, 1, 0, 0, 0)
query += b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0" + struct.pack("!HH", 1, 1)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
sock.settimeout(2.5)
sock.sendto(query, (target, 5353))
found = set()
def skip(data, i):
    while True:
        n = data[i]
        if n == 0: return i + 1
        if n & 0xC0 == 0xC0: return i + 2
        i += n + 1
try:
    while True:
        data, _ = sock.recvfrom(9000)
        qd, an = struct.unpack("!HH", data[4:8])
        i = 12
        for _ in range(qd): i = skip(data, i) + 4
        for _ in range(an):
            i = skip(data, i); rtype, _, _, length = struct.unpack("!HHIH", data[i:i + 10]); i += 10
            if rtype == 1: found.add(socket.inet_ntoa(data[i:i + 4]))
            i += length
except socket.timeout:
    pass
print(",".join(sorted(found)))
'''


def prepare_hub():
    for d in ("bin", "etc-so", "var", "avahi-run", "sysfs"):
        (LAB / d).mkdir(parents=True, exist_ok=True)
    stubs = {
        "systemctl": STUB_SYSTEMCTL,
        # NetworkManager ausente: identidad = MAC del gateway + medio (+ SSID).
        "nmcli": '#!/bin/sh\necho "Error: NetworkManager is not running." >&2\nexit 8\n',
        # Un veth no es una radio: el SSID lo informa este iw (sólo con el enlace arriba).
        "iw": ('#!/bin/sh\nif [ "$2" = "%s" ] && [ "$(cat /sys/class/net/%s/operstate)" = up ]; then\n'
               '  printf "Connected to 02:00:00:00:00:0b (on %s)\\n\\tSSID: Oficina-B\\n"\n'
               'else echo "Not connected."; fi\n') % (WIFI, WIFI, WIFI),
    }
    for name, body in stubs.items():
        (LAB / "bin" / name).write_text(body)
        (LAB / "bin" / name).chmod(0o755)
    (LAB / "api.py").write_text(API)
    (LAB / "mdns_query.py").write_text(MDNS_QUERY)
    # sysfs: NIC "físicas"; operstate apunta al real (se resuelve dentro del namespace del hub).
    for iface in (ETH, WIFI):
        d = LAB / "sysfs" / iface
        (d / "device").mkdir(parents=True, exist_ok=True)
        (d / "type").write_text("1\n")
        (d / "operstate").symlink_to(f"/sys/class/net/{iface}/operstate")
    (LAB / "sysfs" / WIFI / "wireless").mkdir(exist_ok=True)
    env = LAB / "etc-so" / "server-oficina.env"
    env.write_text("SERVER_OFICINA_ENV=production\nSERVER_OFICINA_HOST=127.0.0.1\nSERVER_OFICINA_PORT=8080\n")
    env.chmod(0o640)
    # UFW con la configuración del paquete, aislada del sistema.
    shutil.copytree("/etc/ufw", LAB / "etc-ufw")
    shutil.copy2("/etc/default/ufw", LAB / "default-ufw")
    hub("ufw --force reset >/dev/null && ufw default deny incoming && ufw default allow outgoing "
        "&& ufw --force enable && ufw allow 22/tcp comment ssh")
    # Avahi con la configuración del paquete (sin D-Bus en el laboratorio).
    conf = Path("/etc/avahi/avahi-daemon.conf").read_text()
    (LAB / "avahi-daemon.conf").write_text(conf.replace("[server]\n", "[server]\nenable-dbus=no\n", 1))
    PROCS["avahi"] = subprocess.Popen(
        hub_script(f"exec avahi-daemon --no-drop-root --no-chroot --no-rlimits -f {LAB / 'avahi-daemon.conf'}",
                   avahi=True), env=hub_env(), stdout=open(LAB / "avahi.log", "ab"), stderr=subprocess.STDOUT)
    subprocess.run(hub_script(f"setsid -f python3 {LAB / 'api.py'} >> {LAB / 'api.log'} 2>&1 < /dev/null"),
                   env=hub_env(), check=True)
    wait_until("avahi y API", lambda: (LAB / "avahi-run" / "pid").exists() and (LAB / "api.pid").exists(), 30)


def api_pid() -> str:
    return (LAB / "api.pid").read_text().strip()


def api_host() -> str:
    return next(l.split("=", 1)[1] for l in (LAB / "etc-so" / "server-oficina.env").read_text().splitlines()
                if l.startswith("SERVER_OFICINA_HOST="))


def ufw_numbered() -> str:
    return hub("ufw status numbered").stdout


def lab_rules() -> list[tuple[str, str, str, str]]:
    return sorted((m.group(4), m.group(5), m.group(2), m.group(3)) for m in re.finditer(
        r"^\[\s*(\d+)\]\s+(\d+)/(tcp|udp)\s+on\s+(\S+)\s+ALLOW IN\s+(\S+)\s+#\s*server-oficina-lan", ufw_numbered(),
        re.M))


def rules_for(iface: str, subnet: str, *, syncthing: bool = True, mdns: bool = True) -> list[tuple]:
    ports = [("8080", "tcp")] + ([("22000", "tcp"), ("22000", "udp"), ("21027", "udp")] if syncthing else []) \
        + ([("5353", "udp")] if mdns else [])
    return sorted((iface, subnet, p, proto) for p, proto in ports)


def http_ok(pc: str, ip: str) -> bool:
    result = ns(pc, "curl", "-fsS", "--max-time", "3", f"http://{ip}:8080/api/health", check=False)
    return result.returncode == 0 and '"status": "ok"' in result.stdout


def mdns(pc: str, target: str = "224.0.0.251") -> str:
    return ns(pc, "python3", str(LAB / "mdns_query.py"), "server-oficina.local", target).stdout.strip()


# ---------------------------------------------------------------- Syncthing

def st(node: str, method: str, path: str, payload: dict | None = None):
    args = ["curl", "-fsS", "--max-time", "5", "-H", f"X-API-Key: {API_KEY}", "-X", method]
    if payload is not None:
        args += ["-H", "Content-Type: application/json", "-d", json.dumps(payload)]
    result = ns(node, *args, f"http://127.0.0.1:8384{path}", check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{node} {path}: {result.stderr}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def start_syncthing(node: str):
    home = LAB / f"st-{node}"
    sh(SYNCTHING, "generate", f"--home={home}", "--no-port-probing")
    tree = ET.parse(home / "config.xml")
    options = tree.getroot().find("options")
    # Gate 1 local: descubrimiento local sí; global, relays y NAT no. listenAddress "default"
    # (tcp y quic en 0.0.0.0:22000: todas las interfaces).
    for tag, value in {"globalAnnounceEnabled": "false", "localAnnounceEnabled": "true",
                       "relaysEnabled": "false", "natEnabled": "false", "startBrowser": "false",
                       "crashReportingEnabled": "false", "urAccepted": "-1", "autoUpgradeIntervalH": "0",
                       "reconnectionIntervalS": "5"}.items():
        element = options.find(tag)
        if element is None:
            element = ET.SubElement(options, tag)
        element.text = value
    tree.write(home / "config.xml")
    PROCS[node] = subprocess.Popen(
        ["ip", "netns", "exec", P + node, SYNCTHING, "serve", f"--home={home}", "--gui-address=127.0.0.1:8384",
         f"--gui-apikey={API_KEY}", "--no-browser", "--no-upgrade", "--no-restart"],
        stdout=open(LAB / f"st-{node}.log", "ab"), stderr=subprocess.STDOUT)
    wait_until(f"API Syncthing {node}", lambda: st(node, "GET", "/rest/system/status"), 60)


def configure_syncthing() -> dict[str, str]:
    ids = {n: st(n, "GET", "/rest/system/status")["myID"] for n in ("hub", "pca", "pcb")}
    peers = {"hub": ("pca", "pcb"), "pca": ("hub",), "pcb": ("hub",)}
    for node, others in peers.items():
        for peer in others:
            st(node, "POST", "/rest/config/devices", {"deviceID": ids[peer], "name": peer,
                                                      "addresses": ["dynamic"], "autoAcceptFolders": False})
        folder = LAB / f"st-{node}-folder"
        folder.mkdir(exist_ok=True)
        st(node, "POST", "/rest/config/folders", {
            "id": "lab-sync", "label": "LAB_SYNC", "path": str(folder), "type": "sendreceive",
            "devices": [{"deviceID": ids[p]} for p in others], "rescanIntervalS": 5,
            "fsWatcherEnabled": True, "fsWatcherDelayS": 1, "ignorePerms": True})
    return ids


def connection(node: str, peer_id: str) -> dict:
    return st(node, "GET", "/rest/system/connections")["connections"].get(peer_id, {})


def connected_via(node: str, peer_id: str, prefix: str) -> str | None:
    conn = connection(node, peer_id)
    return conn["address"] if conn.get("connected") and conn.get("address", "").split("://")[-1].startswith(
        prefix) else None


# ---------------------------------------------------------------- escenarios

def scenarios():
    build_network()
    prepare_hub()
    for node in ("hub", "pca", "pcb"):
        start_syncthing(node)
    ids = configure_syncthing()

    # 0 · Nada confiado: UFW deny, API en loopback, ninguna regla propia.
    code, report, err = firewall("trust-current")
    check("0 trust ambiguo", code != 0 and "varias LAN activas" in err, err)
    code, report, _ = firewall("apply", "--require-rules")
    check("0 sin publicar", code == 3 and lab_rules() == [], str(lab_rules()))
    check("0 HTTP bloqueado", not http_ok("pca", HUB_A) and not http_ok("pcb", HUB_B))
    check("0 mDNS unicast bloqueado", mdns("pca", HUB_A) == "" and mdns("pcb", HUB_B) == "")
    record("0_sin_lan_confiable", redes={n["iface"]: n["status"] for n in report["networks"]},
           http_bloqueado=True, mdns_multicast_pc_a=mdns("pca"), mdns_multicast_pc_b=mdns("pcb"),
           nota="Avahi responde al multicast mDNS en cualquier LAN (before.rules de UFW); 8080/22000 cerrados")

    # 1 · Ethernet + Wi-Fi confiadas a la vez, con Syncthing y mDNS.
    code, report, err = firewall("trust-current", "--interface", ETH, "--interface", WIFI)
    check("1 trust", code == 0, err)
    for option in ("enable syncthing", "enable mdns", "api on"):
        firewall(*option.split())
    old_pid = api_pid()
    code, report, err = firewall("apply", "--require-rules", "--sync-api")
    check("1 apply", code == 0 and report["published"] == [ETH, WIFI], f"{code} {err} {report}")
    numbered = ufw_numbered()
    (LAB / "ufw-ethernet-wifi.txt").write_text(numbered)
    check("1 reglas simultáneas", lab_rules() == sorted(rules_for(ETH, LAN_A) + rules_for(WIFI, LAN_B)),
          numbered)
    check("1 SSH intacta", re.search(r"22/tcp\s+ALLOW IN\s+Anywhere\s+# ssh", numbered) is not None, numbered)
    check("1 nunca Anywhere propio", not re.search(r"Anywhere\s+# server-oficina-lan", numbered), numbered)
    wait_until("API reiniciada en 0.0.0.0", lambda: api_pid() != old_pid and http_ok("pca", HUB_A), 20)
    check("1 API 0.0.0.0", api_host() == "0.0.0.0")
    check("1 HTTP por cada LAN", http_ok("pca", HUB_A) and http_ok("pcb", HUB_B))
    check("1 mDNS por LAN", (mdns("pca"), mdns("pcb")) == (HUB_A, HUB_B), f"{mdns('pca')} {mdns('pcb')}")
    check("1 mDNS unicast permitido", (mdns("pca", HUB_A), mdns("pcb", HUB_B)) == (HUB_A, HUB_B))
    via_a = wait_until("hub↔PC-A por Ethernet", lambda: connected_via("hub", ids["pca"], PC_A))
    via_b = wait_until("hub↔PC-B por Wi-Fi", lambda: connected_via("hub", ids["pcb"], PC_B))
    hub_seen_a = wait_until("PC-A ve al hub en su LAN", lambda: connected_via("pca", ids["hub"], HUB_A))
    hub_seen_b = wait_until("PC-B ve al hub en su LAN", lambda: connected_via("pcb", ids["hub"], HUB_B))
    (LAB / "st-pca-folder" / "desde-pc-a.txt").write_text("LAN A\n")
    (LAB / "st-pcb-folder" / "desde-pc-b.txt").write_text("LAN B\n")
    wait_until("archivos de ambas LAN en el hub", lambda: (LAB / "st-hub-folder" / "desde-pc-a.txt").exists()
               and (LAB / "st-hub-folder" / "desde-pc-b.txt").exists(), 120)
    code, audit, _ = firewall("audit")
    check("1 auditoría", code == 0 and audit["problemas"] == [], json.dumps(audit, ensure_ascii=False)[-1500:])
    listeners = audit["escucha"]["syncthing"]
    record("1_ethernet_y_wifi_confiables", reglas=len(lab_rules()), api_host=api_host(),
           mdns_pc_a=mdns("pca"), mdns_pc_b=mdns("pcb"), syncthing_hub_pc_a=via_a, syncthing_hub_pc_b=via_b,
           syncthing_pc_a_ve_hub=hub_seen_a, syncthing_pc_b_ve_hub=hub_seen_b, syncthing_escucha=listeners,
           archivos_sincronizados_por_ambas_lan=True, auditoria_problemas=audit["problemas"],
           avahi=audit["avahi"]["nombre"], enrutamiento=audit["enrutamiento"])

    # 1b · La Latitude no enruta entre LAN (con control positivo).
    PROCS["pcb-web"] = subprocess.Popen(["ip", "netns", "exec", P + "pcb", "python3", "-m", "http.server", "9000",
                                         "--bind", PC_B], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sh("ip", "-n", P + "pca", "route", "add", LAN_B, "via", HUB_A)
    sh("ip", "-n", P + "pcb", "route", "add", LAN_A, "via", HUB_B)
    wait_until("servidor en PC-B", lambda: ns("pcb", "curl", "-fsS", "--max-time", "2", f"http://{PC_B}:9000/",
                                                 check=False).returncode == 0, 20)

    def crosses() -> bool:
        return ns("pca", "curl", "-fsS", "--max-time", "3", f"http://{PC_B}:9000/", check=False).returncode == 0

    no_forward = not crosses()
    ns("hub", "sysctl", "-qw", "net.ipv4.ip_forward=1")  # como hace Docker en la Latitude
    docker_like = not crosses()
    code, audit_fwd, _ = firewall("audit")
    ns("hub", "iptables", "-P", "FORWARD", "ACCEPT")  # control positivo: así SÍ enrutaría
    control = crosses()
    ns("hub", "iptables", "-P", "FORWARD", "DROP")
    ns("hub", "sysctl", "-qw", "net.ipv4.ip_forward=0")
    check("1b sin forwarding", no_forward and docker_like and not crosses())
    check("1b control positivo", control, "el control no cruzó: la prueba no sería concluyente")
    check("1b auditoría con ip_forward=1", audit_fwd["enrutamiento"]["problemas"] == [], str(audit_fwd))
    sh("ip", "-n", P + "pca", "route", "del", LAN_B)
    sh("ip", "-n", P + "pcb", "route", "del", LAN_A)
    record("1b_no_enruta_entre_lan", ip_forward_0_bloquea=no_forward, ip_forward_1_con_ufw_bloquea=docker_like,
           control_positivo_forward_accept_cruza=control, auditoria_ip_forward_1=audit_fwd["enrutamiento"])

    # 2 · Cae la Wi-Fi: Ethernet sigue sin tocarse (ni reglas, ni API, ni Syncthing).
    started_a = connection("hub", ids["pca"])["startedAt"]
    pid = api_pid()
    link_down(WIFI)
    code, report, _ = firewall("apply", "--sync-api")
    check("2 reglas", lab_rules() == rules_for(ETH, LAN_A), str(lab_rules()))
    check("2 sólo se borró Wi-Fi", all(r["iface"] == WIFI for r in report["removed"]) and report["added"] == [],
          str(report))
    check("2 API intacta", api_host() == "0.0.0.0" and api_pid() == pid)
    check("2 HTTP Ethernet", http_ok("pca", HUB_A) and not http_ok("pcb", HUB_B))
    check("2 mDNS Ethernet", mdns("pca") == HUB_A)
    time.sleep(8)
    check("2 Syncthing Ethernet sin reconectar", connection("hub", ids["pca"]).get("connected")
          and connection("hub", ids["pca"])["startedAt"] == started_a)
    started_b = connection("hub", ids["pcb"]).get("startedAt")
    (LAB / "st-pca-folder" / "durante-caida-wifi.txt").write_text("sigue por Ethernet\n")
    wait_until("sincroniza por Ethernet con la Wi-Fi caída",
               lambda: (LAB / "st-hub-folder" / "durante-caida-wifi.txt").exists(), 90)
    record("2_cae_wifi", reglas=lab_rules(), api_pid_sin_cambio=True, http_ethernet=True,
           syncthing_ethernet_misma_conexion=started_a, archivo_sincronizado_por_ethernet=True)

    # 3 · Vuelve la Wi-Fi: ambas otra vez, sin nueva decisión de confianza.
    link_up(WIFI)
    code, report, _ = firewall("apply", "--sync-api")
    check("3 reglas", lab_rules() == sorted(rules_for(ETH, LAN_A) + rules_for(WIFI, LAN_B)), str(lab_rules()))
    check("3 HTTP", http_ok("pca", HUB_A) and http_ok("pcb", HUB_B))
    wait_until("mDNS Wi-Fi de vuelta", lambda: mdns("pcb") == HUB_B, 30)
    via_b = wait_until("Syncthing PC-B conectado por Wi-Fi", lambda: connected_via("hub", ids["pcb"], PC_B))
    after_b = connection("hub", ids["pcb"])["startedAt"]
    (LAB / "st-pcb-folder" / "tras-volver-wifi.txt").write_text("otra vez por Wi-Fi\n")
    wait_until("sincroniza por Wi-Fi al volver", lambda: (LAB / "st-hub-folder" / "tras-volver-wifi.txt").exists(),
               90)
    record("3_vuelve_wifi", reglas=len(lab_rules()), syncthing_hub_pc_b=via_b, mdns_pc_b=mdns("pcb"),
           syncthing_wifi_startedAt_antes=started_b, syncthing_wifi_startedAt_despues=after_b,
           sesion_tcp_nueva=after_b != started_b, archivo_sincronizado_por_wifi=True,
           nota="con un corte breve la sesión TCP puede sobrevivir; lo exigible es que vuelva a sincronizar")

    # 4 · Cae Ethernet: la Wi-Fi sigue.
    started_b = connection("hub", ids["pcb"])["startedAt"]
    link_down(ETH)
    code, report, _ = firewall("apply", "--sync-api")
    check("4 reglas", lab_rules() == rules_for(WIFI, LAN_B), str(lab_rules()))
    check("4 HTTP Wi-Fi", http_ok("pcb", HUB_B) and not http_ok("pca", HUB_A) and api_host() == "0.0.0.0")
    time.sleep(8)
    check("4 Syncthing Wi-Fi sin reconectar", connection("hub", ids["pcb"]).get("connected")
          and connection("hub", ids["pcb"])["startedAt"] == started_b)
    (LAB / "st-pcb-folder" / "durante-caida-ethernet.txt").write_text("sigue por Wi-Fi\n")
    wait_until("sincroniza por Wi-Fi con el cable caído",
               lambda: (LAB / "st-hub-folder" / "durante-caida-ethernet.txt").exists(), 90)
    record("4_cae_ethernet", reglas=lab_rules(), http_wifi=True, syncthing_wifi_misma_conexion=started_b,
           archivo_sincronizado_por_wifi=True)

    # 5 · Vuelve Ethernet.
    link_up(ETH)
    firewall("apply", "--sync-api")
    check("5 reglas", lab_rules() == sorted(rules_for(ETH, LAN_A) + rules_for(WIFI, LAN_B)), str(lab_rules()))
    via_a = wait_until("Syncthing PC-A reconecta por Ethernet", lambda: connected_via("hub", ids["pca"], PC_A))
    check("5 HTTP", http_ok("pca", HUB_A) and http_ok("pcb", HUB_B))
    record("5_vuelve_ethernet", reglas=len(lab_rules()), syncthing_hub_pc_a=via_a)

    # 6 · Ethernet en una LAN desconocida (otro router): la Wi-Fi no se entera.
    router_mac = sh("ip", "-n", P + "lana", "link", "show", "br0").stdout.split("link/ether ")[1].split()[0]
    sh("ip", "-n", P + "lana", "link", "set", "br0", "address", "02:00:00:00:99:99")
    ns("hub", "ip", "neigh", "flush", "dev", ETH)
    code, report, _ = firewall("apply", "--require-rules", "--sync-api")
    status = {n["iface"]: n["status"] for n in report["networks"]}
    check("6 estados", status == {ETH: "no_confiable", WIFI: "confiable"} and code == 0, str(status))
    check("6 reglas", lab_rules() == rules_for(WIFI, LAN_B), str(lab_rules()))
    check("6 HTTP", http_ok("pcb", HUB_B) and not http_ok("pca", HUB_A) and api_host() == "0.0.0.0")
    code, _, err = firewall("trust-current")
    check("6 no se confía por estar enchufada", code != 0 and "varias LAN activas" in err, err)
    record("6_ethernet_en_lan_desconocida", estados=status, reglas=lab_rules())
    sh("ip", "-n", P + "lana", "link", "set", "br0", "address", router_mac)
    ns("hub", "ip", "neigh", "flush", "dev", ETH)
    firewall("apply", "--sync-api")
    check("6b router original", lab_rules() == sorted(rules_for(ETH, LAN_A) + rules_for(WIFI, LAN_B))
          and http_ok("pca", HUB_A), str(lab_rules()))
    record("6b_router_original_de_vuelta_sin_nueva_confianza", reglas=len(lab_rules()))

    # 7 · Ninguna LAN confiable: API sólo en loopback; al volver, 0.0.0.0.
    link_down(ETH)
    link_down(WIFI)
    pid = api_pid()
    code, report, _ = firewall("apply", "--sync-api")
    check("7 sin reglas", lab_rules() == [] and api_host() == "127.0.0.1", f"{lab_rules()} {api_host()}")
    wait_until("API reiniciada en loopback", lambda: api_pid() != pid, 20)
    listening = hub("ss -H -lnt 'sport = :8080'").stdout
    check("7 escucha loopback", "127.0.0.1:8080" in listening and "0.0.0.0:8080" not in listening, listening)
    record("7_ninguna_lan_api_loopback", api_host=api_host(), escucha=listening.split()[3:4])
    link_up(ETH)
    link_up(WIFI)
    pid = api_pid()
    firewall("apply", "--sync-api")
    wait_until("API de vuelta en 0.0.0.0", lambda: api_pid() != pid and http_ok("pca", HUB_A), 20)
    check("7 vuelven ambas", http_ok("pcb", HUB_B) and api_host() == "0.0.0.0" and len(lab_rules()) == 10)
    record("7b_vuelven_ambas", api_host=api_host(), reglas=len(lab_rules()))

    EVIDENCE["ufw_ethernet_wifi"] = numbered.splitlines()
    EVIDENCE["avahi"] = [l for l in (LAB / "avahi.log").read_text().splitlines()
                         if "address record" in l or "Host name is" in l][:6]
    EVIDENCE["result"] = "MULTI_LAN_LAB_OK"
    print("MULTI_LAN_LAB_OK", flush=True)


def cleanup():
    for name, proc in list(PROCS.items()):
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
    if (LAB / "api.pid").exists():
        subprocess.run(["kill", (LAB / "api.pid").read_text().strip()], capture_output=True)
    destroy_network()


def main() -> int:
    if os.geteuid() != 0:
        print("multi_lan_lab requiere root (namespaces de red)", file=sys.stderr)
        return 2
    missing = [t for t in ("ip", "ufw", "avahi-daemon", "curl", "iptables") if not shutil.which(t)]
    if missing or not SYNCTHING:
        print(f"faltan herramientas: {missing or ''} {'' if SYNCTHING else 'SYNCTHING_BIN'}", file=sys.stderr)
        return 2
    destroy_network()
    if LAB.exists():
        shutil.rmtree(LAB)
    LAB.mkdir(parents=True)
    try:
        scenarios()
        return 0
    finally:
        cleanup()
        (LAB / "evidence.json").write_text(json.dumps(EVIDENCE, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - toda falla queda como evidencia
        EVIDENCE["result"] = f"FAIL: {exc.__class__.__name__}: {exc}"
        (LAB / "evidence.json").write_text(json.dumps(EVIDENCE, indent=2, ensure_ascii=False))
        print(f"MULTI_LAN_LAB_FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
