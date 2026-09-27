"""Reconciliador UFW multi-interfaz: Ethernet + Wi-Fi a la vez, confianza por LAN.

La Latitude puede estar en dos LAN de la oficina simultáneamente (cable y
Wi-Fi). Cada LAN se identifica por MAC del gateway + perfil de NetworkManager
(si existe) + SSID en Wi-Fi, nunca por el nombre de la interfaz. Se simulan
``/sys/class/net``, ``ip``, ``iw``, ``nmcli``, ``ping``, ``systemctl`` y ``ufw``
(con el formato real de ``ufw status numbered`` de UFW 0.36.2).
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ETH, WIFI = "enp0s31f6", "wlp2s0"
GW_A, GW_B, OTHER_GW = "aa:bb:cc:00:00:0a", "aa:bb:cc:00:00:0b", "aa:bb:cc:99:99:99"
NM_ETH, NM_WIFI = "11111111-0000-0000-0000-00000000000a", "22222222-0000-0000-0000-00000000000b"
LAN_A, LAN_B = "192.168.10.0/24", "192.168.48.0/24"
DEFAULTS = {
    "eth": {"name": ETH, "kind": "wired", "ip": "192.168.10.23/24", "gw": "192.168.10.1", "gw_mac": GW_A},
    "wifi": {"name": WIFI, "kind": "wifi", "ip": "192.168.48.109/24", "gw": "192.168.48.1", "gw_mac": GW_B,
             "ssid": "OficinaADQ"},
}
SSH = {"display": ["22/tcp", "Anywhere"], "comment": "ssh"}

FAKE_UFW = r'''#!PYTHON
import json, os, sys
db = os.environ["FAKE_UFW_DB"]
state = json.load(open(db)) if os.path.exists(db) else {
    "active": True, "default": "deny", "rules": [], "fail_allow": False, "ops": []}
args = sys.argv[1:]
def save(): json.dump(state, open(db, "w"))
def show(r):
    if "display" in r:
        to, frm = r["display"]
    else:
        a = r["args"]
        to, frm = f"{a[8]}/{a[10]} on {a[2]}", a[4]
    return f"{to:<26} ALLOW IN    {frm:<26} # {r['comment']}"  # ufw: "%-26s " por columna
status = "Status: active" if state["active"] else "Status: inactive"
if args == ["status"]:
    print(status)
elif args == ["status", "verbose"]:
    print(status)
    if state["active"]:
        print(f"Logging: on (low)\nDefault: {state['default']} (incoming), allow (outgoing), disabled (routed)")
elif args == ["status", "numbered"]:
    print(status)
    if state["active"]:
        print("\n     To                         Action      From\n     --                         ------      ----")
        for i, r in enumerate(state["rules"], 1):
            print(f"[{i:2d}] {show(r)}")
elif args[:2] == ["--force", "delete"]:
    r = state["rules"].pop(int(args[2]) - 1); state["ops"].append(["delete", show(r)]); save()
elif args[0] == "allow":
    if state.get("fail_allow"):
        print("ERROR: simulated failure", file=sys.stderr); sys.exit(1)
    i = args.index("comment")
    r = {"args": args[1:i], "comment": args[i + 1]}
    state["rules"].append(r); state["ops"].append(["allow", show(r)]); save()
else:
    sys.exit(2)
'''

FAKE_IP = r'''#!PYTHON
import json, os, sys
n = json.load(open(os.environ["FAKE_NET"]))
ifaces = [i for i in n["ifaces"] if i.get("addr", True)]
args = sys.argv[1:]
if "neigh" in args:
    gw, dev = args[args.index("show") + 1], args[args.index("dev") + 1]
    for i in ifaces:
        if i["name"] == dev and i.get("gw") == gw:
            print(f"{gw} lladdr {i['gw_mac']} REACHABLE" if i.get("gw_mac") else f"{gw}  INCOMPLETE")
elif "addr" in args:
    for idx, i in enumerate(ifaces, 2):
        print(f"{idx}: {i['name']}    inet {i['ip']} brd 0.0.0.0 scope global dynamic noprefixroute "
              f"{i['name']}\\       valid_lft 86000sec preferred_lft 86000sec")
elif "default" in args:
    for i in ifaces:
        if i.get("gw"):
            metric = 100 if i["kind"] == "wired" else 600
            print(f"default via {i['gw']} dev {i['name']} proto dhcp src {i['ip'].split('/')[0]} metric {metric}")
'''


@pytest.fixture()
def lan(tmp_path: Path, monkeypatch):
    bin_dir, sysfs = tmp_path / "bin", tmp_path / "sys" / "class" / "net"
    bin_dir.mkdir()
    net = tmp_path / "net.json"
    env_file = tmp_path / "etc" / "server-oficina.env"
    env_file.parent.mkdir()
    env_file.write_text("SERVER_OFICINA_ENV=production\nSERVER_OFICINA_HOST=127.0.0.1\nSERVER_OFICINA_PORT=8080\n")
    env_file.chmod(0o640)

    def write(name: str, body: str):
        path = bin_dir / name
        path.write_text(body.replace("#!PYTHON", f"#!{sys.executable}"))
        path.chmod(0o755)

    write("ufw", FAKE_UFW)
    write("ip", FAKE_IP)
    write("iw", r'''#!PYTHON
import json, os, sys
n = json.load(open(os.environ["FAKE_NET"]))
i = next((i for i in n["ifaces"] if i["name"] == sys.argv[2]), {})
print(f"Connected to 02:00:00:00:00:01 (on {sys.argv[2]})\n\tSSID: {i.get('ssid', '')}\n\tfreq: 5180"
      if i.get("ssid") is not None else "Not connected.")
''')
    write("nmcli", r'''#!PYTHON
import json, os, sys
n = json.load(open(os.environ["FAKE_NET"]))
if n["nm"] == "absent":
    print("Error: NetworkManager is not running.", file=sys.stderr); sys.exit(8)
if n["nm"] == "error":
    print("Error: timeout", file=sys.stderr); sys.exit(1)
print("lo:00000000-0000-0000-0000-000000000000")
for i in n["ifaces"]:
    if i.get("nm_uuid") and i.get("addr", True):
        print(f"{i['name']}:{i['nm_uuid']}")
''')
    write("ping", "#!/bin/sh\nexit 0\n")
    write("systemctl", f'#!/bin/sh\necho "$*" >> "{tmp_path / "systemctl.log"}"\n')
    for key, value in {
        "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_UFW_DB": str(tmp_path / "ufw.json"),
        "FAKE_NET": str(net), "SO_LAN_FIREWALL_SYSFS": str(sysfs), "SO_ENV_FILE": str(env_file),
        "SO_LAN_FIREWALL_CONF": str(tmp_path / "etc" / "lan-firewall.json"),
        "SO_LAN_FIREWALL_STATE": str(tmp_path / "var" / "state.json"),
        "SO_LAN_FIREWALL_LOCK": str(tmp_path / "lan-firewall.lock"),
    }.items():
        monkeypatch.setenv(key, value)

    def load(hold_seconds: int = 600):
        monkeypatch.setenv("SO_LAN_FIREWALL_HOLD_SECONDS", str(hold_seconds))
        spec = importlib.util.spec_from_file_location("lan_firewall", ROOT / "scripts" / "lan_firewall.py")
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, "lan_firewall", module)
        spec.loader.exec_module(module)
        return module

    class Lab:
        fw = load()

        @staticmethod
        def reload(**kwargs):
            Lab.fw = load(**kwargs)

        @staticmethod
        def set(*, eth=None, wifi=None, nm="absent", extra=()):
            """eth/wifi: dict de cambios sobre la LAN por defecto, o None = interfaz sin red."""
            import shutil
            shutil.rmtree(sysfs, ignore_errors=True)
            ifaces = [{**DEFAULTS[k], **v} for k, v in (("eth", eth), ("wifi", wifi)) if v is not None]
            # Siempre presentes y nunca candidatas: Docker (RFC1918), un veth y una NIC esclava de un bridge.
            virtual = [{"name": "docker0", "kind": "virtual", "ip": "172.17.0.1/16"},
                       {"name": "veth1a2b3c", "kind": "virtual", "ip": "10.99.0.2/24"},
                       {"name": "enp4s0", "kind": "wired", "ip": "10.77.0.2/24", "gw": "10.77.0.1",
                        "gw_mac": GW_A, "master": "br0"}, *extra]
            for i in ifaces + virtual:
                d = sysfs / i["name"]
                d.mkdir(parents=True)
                (d / "type").write_text("1\n")
                (d / "operstate").write_text("up\n" if i.get("up", True) else "down\n")
                if i["kind"] != "virtual":
                    (d / "device").mkdir()
                if i["kind"] == "wifi":
                    (d / "wireless").mkdir()
                if i.get("master"):
                    (d / "master").mkdir()
            net.write_text(json.dumps({"ifaces": ifaces + virtual, "nm": nm}))

        @staticmethod
        def ufw(**state):
            db = Path(os.environ["FAKE_UFW_DB"])
            current = json.loads(db.read_text()) if db.exists() else {
                "active": True, "default": "deny", "rules": [], "fail_allow": False, "ops": []}
            if state:
                current.update(state)
                db.write_text(json.dumps(current))
            return current

        @staticmethod
        def rules() -> list[tuple[str, str, str, str]]:
            """Reglas propias en UFW: (interfaz, subred, puerto, proto)."""
            return sorted((r["args"][2], r["args"][4], r["args"][8], r["args"][10])
                          for r in Lab.ufw()["rules"] if r["comment"] == "server-oficina-lan")

        @staticmethod
        def ops() -> list:
            ops = Lab.ufw()["ops"]
            Lab.ufw(ops=[])
            return ops

        @staticmethod
        def run(*args) -> int:
            return Lab.fw.main(list(args))

        @staticmethod
        def report(*args) -> dict:
            """Ejecuta y devuelve el JSON LAN_FIREWALL impreso."""
            import contextlib
            import io
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = Lab.fw.main(list(args))
            data = json.loads(out.getvalue().split("LAN_FIREWALL ", 1)[1])
            data["_exit"] = code
            return data

        @staticmethod
        def api_host() -> str:
            return next(l.split("=", 1)[1] for l in Lab.env_file.read_text().splitlines()
                        if l.startswith("SERVER_OFICINA_HOST="))

    Lab.env_file = env_file
    Lab.systemctl_log = tmp_path / "systemctl.log"
    Lab.set(eth={})
    return Lab


def web(iface: str, subnet: str) -> tuple:
    return (iface, subnet, "8080", "tcp")


def trust_both(lan):
    lan.set(eth={}, wifi={})
    assert lan.run("trust-current", "--interface", ETH, "--interface", WIFI) == 0
    assert lan.rules() == [web(ETH, LAN_A), web(WIFI, LAN_B)]
    lan.ops()


# ================================================================ multi-LAN (casos pedidos)

# 1 · Ethernet sola confiable
def test_ethernet_only_trusted(lan):
    lan.set(eth={})
    assert lan.run("trust-current") == 0
    assert lan.rules() == [web(ETH, LAN_A)]
    assert lan.run("apply", "--require-rules") == 0


# 2 · Wi-Fi sola confiable
def test_wifi_only_trusted(lan):
    lan.set(wifi={})
    assert lan.run("trust-current") == 0
    assert lan.rules() == [web(WIFI, LAN_B)]
    assert lan.run("apply", "--require-rules") == 0


# 3 · Ethernet + Wi-Fi confiables a la vez
def test_ethernet_and_wifi_trusted_simultaneously(lan):
    lan.set(eth={}, wifi={})
    with pytest.raises(SystemExit, match="varias LAN activas"):
        lan.run("trust-current")  # nunca se elige una LAN por estar enchufada
    assert lan.rules() == []
    trust_both(lan)
    conf = json.loads(Path(os.environ["SO_LAN_FIREWALL_CONF"]).read_text())
    ids = sorted(e["id"] for e in conf["trusted_networks"])
    assert ids == [f"medium=wifi|ssid=OficinaADQ|gw_mac={GW_B}", f"medium=wired|gw_mac={GW_A}"]
    assert all("iface" not in e["components"] for e in conf["trusted_networks"])
    report = lan.report("apply", "--require-rules")
    assert report["_exit"] == 0 and report["published"] == [ETH, WIFI]


# 4 · se cae Wi-Fi y Ethernet sigue
def test_wifi_drops_ethernet_keeps_serving(lan):
    trust_both(lan)
    lan.set(eth={})  # Wi-Fi sin red
    report = lan.report("apply", "--require-rules")
    assert report["_exit"] == 0 and report["published"] == [ETH] and report["ausentes"] == [WIFI]
    assert lan.rules() == [web(ETH, LAN_A)]
    ops = lan.ops()
    assert [op for op, _ in ops] == ["delete"] and WIFI in ops[0][1]  # Ethernet no se tocó


# 5 · se cae Ethernet y Wi-Fi sigue
def test_ethernet_drops_wifi_keeps_serving(lan):
    trust_both(lan)
    lan.set(wifi={}, eth={"up": False})  # cable desconectado: sysfs presente, operstate down
    assert lan.run("apply", "--require-rules") == 0
    assert lan.rules() == [web(WIFI, LAN_B)]
    assert all(ETH in text for _, text in lan.ops())


# 6 · regresa la interfaz caída
def test_dropped_interface_returns_without_new_trust(lan):
    trust_both(lan)
    lan.set(eth={})
    lan.run("apply")
    lan.set(eth={}, wifi={})
    assert lan.run("apply", "--require-rules") == 0
    assert lan.rules() == [web(ETH, LAN_A), web(WIFI, LAN_B)]
    assert [op for op, _ in lan.ops()] == ["delete", "allow"]  # sólo Wi-Fi: salir y volver


# 7 · Wi-Fi confiable + Ethernet en una LAN desconocida
def test_trusted_wifi_and_unknown_ethernet(lan):
    lan.set(wifi={})
    lan.run("trust-current")
    lan.set(wifi={}, eth={"ip": "10.0.5.40/24", "gw": "10.0.5.1", "gw_mac": OTHER_GW})
    report = lan.report("apply", "--require-rules")
    assert report["_exit"] == 0
    assert {n["iface"]: n["status"] for n in report["networks"]} == {ETH: "no_confiable", WIFI: "confiable"}
    assert lan.rules() == [web(WIFI, LAN_B)]
    with pytest.raises(SystemExit):
        lan.run("trust-current")  # enchufar un cable no basta para confiar
    assert lan.rules() == [web(WIFI, LAN_B)]


# 8 · Ethernet confiable + Wi-Fi desconocida
def test_trusted_ethernet_and_unknown_wifi(lan):
    lan.set(eth={})
    lan.run("trust-current")
    lan.set(eth={}, wifi={"ssid": "Hotel-Invitados", "gw_mac": OTHER_GW, "ip": "192.168.1.30/24",
                          "gw": "192.168.1.1"})
    assert lan.run("apply", "--require-rules") == 0
    assert lan.rules() == [web(ETH, LAN_A)]


# 9 · dos LAN confiables con subredes diferentes (incluida 172.16/12)
def test_two_trusted_lans_with_different_subnets(lan):
    lan.set(eth={"ip": "172.20.4.8/22", "gw": "172.20.4.1"}, wifi={"ip": "10.40.0.9/16", "gw": "10.40.0.1"})
    lan.run("trust-current", "--interface", ETH, "--interface", WIFI)
    assert lan.rules() == [web(ETH, "172.20.4.0/22"), web(WIFI, "10.40.0.0/16")]


# 10 · cambio DHCP independiente en Ethernet
def test_independent_dhcp_change_on_ethernet(lan):
    trust_both(lan)
    lan.set(eth={"ip": "192.168.20.77/24", "gw": "192.168.20.1"}, wifi={})  # mismo router, otro rango
    assert lan.run("apply", "--require-rules") == 0
    assert lan.rules() == [web(ETH, "192.168.20.0/24"), web(WIFI, LAN_B)]
    assert all(ETH in text for _, text in lan.ops())  # Wi-Fi intacta


# 11 · cambio DHCP independiente en Wi-Fi
def test_independent_dhcp_change_on_wifi(lan):
    trust_both(lan)
    lan.set(eth={}, wifi={"ip": "192.168.49.12/24"})  # nueva IP y nueva subred, mismo router
    assert lan.run("apply", "--require-rules") == 0
    assert lan.rules() == [web(ETH, LAN_A), web(WIFI, "192.168.49.0/24")]
    assert all(WIFI in text for _, text in lan.ops())


# 12 · cambio de router en una LAN no afecta a la otra
def test_router_change_in_one_lan_does_not_affect_the_other(lan):
    trust_both(lan)
    lan.set(eth={"gw_mac": OTHER_GW}, wifi={})
    report = lan.report("apply", "--require-rules")
    assert report["_exit"] == 0 and report["published"] == [WIFI]
    assert lan.rules() == [web(WIFI, LAN_B)]
    assert all(ETH in text for _, text in lan.ops())
    assert lan.run("trust-current", "--interface", ETH) == 0  # decisión explícita tras cambiar el router
    assert lan.rules() == [web(ETH, LAN_A), web(WIFI, LAN_B)]


# 13 · UFW mantiene reglas simultáneas por interfaz; reaplicar no toca nada
def test_ufw_keeps_simultaneous_rules_per_interface(lan):
    lan.ufw(rules=[SSH])
    trust_both(lan)
    lan.run("enable", "syncthing")
    lan.run("enable", "mdns")
    lan.ops()
    for _ in range(3):
        assert lan.run("apply", "--require-rules") == 0
    assert lan.ops() == []
    rules = lan.rules()
    assert len(rules) == 10
    assert {(i, s) for i, s, _, _ in rules} == {(ETH, LAN_A), (WIFI, LAN_B)}  # nunca cruzadas
    assert SSH in lan.ufw()["rules"]
    shown = "\n".join(text for _, text in lan.ufw()["ops"])
    assert "Anywhere" not in shown


# 14 · puertos de Syncthing en ambas LAN
def test_syncthing_ports_on_both_lans(lan):
    trust_both(lan)
    lan.run("enable", "syncthing")
    expected = [(iface, subnet, port, proto)
                for iface, subnet in ((ETH, LAN_A), (WIFI, LAN_B))
                for port, proto in (("21027", "udp"), ("22000", "tcp"), ("22000", "udp"), ("8080", "tcp"))]
    assert lan.rules() == sorted(expected)


# 15 · mDNS 5353/udp sólo en las interfaces de LAN confiables
def test_mdns_limited_to_trusted_interfaces(lan):
    lan.set(wifi={})
    lan.run("trust-current")
    lan.run("enable", "mdns")
    lan.set(wifi={}, eth={"ip": "10.0.5.40/24", "gw": "10.0.5.1", "gw_mac": OTHER_GW})
    lan.run("apply")
    assert [r for r in lan.rules() if r[2] == "5353"] == [(WIFI, LAN_B, "5353", "udp")]
    assert not any(r[0] == ETH for r in lan.rules())


# 16 · ninguna LAN confiable → API sólo en loopback; alguna → 0.0.0.0
def test_api_host_follows_trusted_lans(lan):
    trust_both(lan)
    lan.run("api", "on")
    assert lan.run("apply", "--sync-api") == 0
    assert lan.api_host() == "0.0.0.0"
    assert "try-restart server-oficina.service" in lan.systemctl_log.read_text()
    lan.systemctl_log.write_text("")
    lan.set(eth={})  # cae Wi-Fi: queda Ethernet
    lan.run("apply", "--sync-api")
    assert lan.api_host() == "0.0.0.0" and lan.systemctl_log.read_text() == ""  # sin reinicio
    lan.set()  # cae también Ethernet
    report = lan.report("apply", "--sync-api")
    assert lan.api_host() == "127.0.0.1" and report["api"]["cambiado"] is True
    lan.set(eth={"gw_mac": OTHER_GW})  # sólo una LAN desconocida
    lan.run("apply", "--sync-api")
    assert lan.api_host() == "127.0.0.1"
    lan.set(wifi={})  # vuelve la Wi-Fi confiable
    lan.run("apply", "--sync-api")
    assert lan.api_host() == "0.0.0.0"


def test_api_loopback_when_ufw_not_protecting(lan):
    trust_both(lan)
    lan.run("api", "on")
    lan.run("apply", "--sync-api")
    assert lan.api_host() == "0.0.0.0"
    lan.ufw(default="allow")
    lan.run("apply", "--sync-api")
    assert lan.api_host() == "127.0.0.1"
    lan.ufw(default="deny", active=False)  # alguien desactivó UFW a mano
    lan.run("apply", "--sync-api")
    assert lan.api_host() == "127.0.0.1"


def test_api_host_untouched_without_publication_intent(lan):
    trust_both(lan)
    lan.run("apply", "--sync-api")
    assert lan.api_host() == "127.0.0.1" and not lan.systemctl_log.exists()
    lan.env_file.write_text(lan.env_file.read_text().replace("127.0.0.1", "0.0.0.0"))
    lan.run("api", "off")
    lan.run("apply", "--sync-api")
    assert lan.api_host() == "127.0.0.1"
    assert oct(lan.env_file.stat().st_mode & 0o777) == "0o640"


# ================================================================ identidad (por LAN)

def test_same_network_new_ip_keeps_access_without_intervention(lan):
    lan.run("trust-current")
    lan.set(eth={"ip": "192.168.10.201/24"})
    assert lan.run("apply", "--require-rules") == 0
    assert lan.rules() == [web(ETH, LAN_A)]


def test_same_ssid_different_network_is_not_trusted(lan):
    lan.set(wifi={})
    lan.run("trust-current")
    lan.set(wifi={"gw_mac": OTHER_GW})
    assert lan.run("apply", "--require-rules") == 3
    assert lan.rules() == []


def test_same_ethernet_interface_different_network_is_not_trusted(lan):
    lan.run("trust-current")
    lan.set(eth={"gw_mac": OTHER_GW})
    assert lan.run("apply", "--require-rules") == 3
    assert lan.rules() == []


def test_trust_is_by_network_not_by_interface_name(lan):
    """La LAN confiada por cable sigue siéndolo si el adaptador cambia de nombre (p. ej. USB)."""
    lan.run("trust-current")
    lan.set(extra=[{"name": "enx00e04c680001", "kind": "wired", "ip": "192.168.10.50/24", "gw": "192.168.10.1",
                    "gw_mac": GW_A}])
    assert lan.run("apply", "--require-rules") == 0
    assert lan.rules() == [web("enx00e04c680001", LAN_A)]


def test_same_nm_profile_on_another_router_is_not_trusted(lan):
    """Un perfil 'Wired connection 1' se activa en cualquier LAN: el UUID solo no basta."""
    lan.set(eth={"nm_uuid": NM_ETH}, nm="ok")
    lan.run("trust-current")
    lan.set(eth={"nm_uuid": NM_ETH, "gw_mac": OTHER_GW}, nm="ok")
    assert lan.run("apply", "--require-rules") == 3


def test_same_router_but_other_nm_profile_is_not_trusted(lan):
    lan.set(wifi={"nm_uuid": NM_WIFI}, nm="ok")
    lan.run("trust-current")
    lan.set(wifi={"nm_uuid": "99999999-0000-0000-0000-000000000000"}, nm="ok")
    assert lan.run("apply", "--require-rules") == 3


def test_nm_profiles_are_read_per_interface(lan):
    lan.set(eth={"nm_uuid": NM_ETH}, wifi={"nm_uuid": NM_WIFI}, nm="ok")
    lan.run("trust-current", "--interface", ETH, "--interface", WIFI)
    conf = json.loads(Path(os.environ["SO_LAN_FIREWALL_CONF"]).read_text())
    assert sorted(e["components"]["nm"] for e in conf["trusted_networks"]) == [NM_ETH, NM_WIFI]
    lan.set(eth={"nm_uuid": NM_WIFI}, wifi={"nm_uuid": NM_ETH}, nm="ok")  # perfiles cruzados
    assert lan.run("apply", "--require-rules") == 3


def test_new_network_gets_nothing_until_explicit_trust(lan):
    lan.run("trust-current")
    lan.set(eth={"ip": "192.168.1.30/24", "gw": "192.168.1.1", "gw_mac": OTHER_GW})
    assert lan.run("apply", "--require-rules") == 3
    assert lan.run("trust-current") == 0
    assert lan.rules() == [web(ETH, "192.168.1.0/24")]


def test_first_apply_never_trusts_implicitly(lan):
    lan.set(eth={}, wifi={})
    assert lan.run("apply", "--require-rules") == 3
    assert lan.rules() == []


@pytest.mark.parametrize("ip,gw", [("203.0.113.9/24", "203.0.113.1"), ("100.64.0.9/24", "100.64.0.1"),
                                   ("8.8.8.9/24", "8.8.8.1")])
def test_public_network_is_never_opened(lan, ip, gw):
    lan.set(eth={"ip": ip, "gw": gw})
    with pytest.raises(SystemExit):
        lan.run("trust-current")
    assert lan.run("apply", "--require-rules") == 3
    assert lan.rules() == []


def test_temporary_identity_loss_holds_only_that_interface(lan):
    trust_both(lan)
    lan.set(eth={}, wifi={"gw_mac": None})  # ARP del gateway Wi-Fi vacío
    report = lan.report("apply", "--require-rules")
    assert report["_exit"] == 0 and report["hold"] == [WIFI] and report["published"] == [ETH]
    assert lan.rules() == [web(ETH, LAN_A), web(WIFI, LAN_B)]
    lan.reload(hold_seconds=0)  # vence el plazo
    lan.run("apply")
    assert lan.rules() == [web(ETH, LAN_A)]
    lan.set(eth={}, wifi={})  # la identidad vuelve
    lan.run("apply")
    assert lan.rules() == [web(ETH, LAN_A), web(WIFI, LAN_B)]


def test_hold_alone_is_not_ready(lan):
    lan.run("trust-current")
    lan.set(eth={"gw_mac": None})
    assert lan.run("apply", "--require-rules") == 3
    assert lan.rules() == [web(ETH, LAN_A)]


def test_identity_loss_with_changed_subnet_closes_immediately(lan):
    lan.run("trust-current")
    lan.set(eth={"gw_mac": None, "ip": "10.9.0.5/24", "gw": "10.9.0.1"})
    lan.run("apply")
    assert lan.rules() == []


def test_networkmanager_error_is_identity_loss_not_new_network(lan):
    lan.set(eth={"nm_uuid": NM_ETH}, nm="ok")
    lan.run("trust-current")
    lan.set(eth={"nm_uuid": NM_ETH}, nm="error")
    lan.run("apply")
    assert lan.rules() == [web(ETH, LAN_A)]


def test_wifi_without_ssid_or_gateway_is_never_trusted_blindly(lan):
    lan.set(wifi={"ssid": ""})
    with pytest.raises(SystemExit):
        lan.run("trust-current")
    lan.set(wifi={"gw_mac": None})
    with pytest.raises(SystemExit):
        lan.run("trust-current")
    lan.set(wifi={"gw": None})  # sin gateway: sin identidad verificable
    with pytest.raises(SystemExit):
        lan.run("trust-current")


def test_trust_is_all_or_nothing_and_needs_a_real_interface(lan):
    lan.set(eth={}, wifi={"gw_mac": None})
    with pytest.raises(SystemExit):
        lan.run("trust-current", "--interface", ETH, "--interface", WIFI)
    assert not Path(os.environ["SO_LAN_FIREWALL_CONF"]).exists()
    for bogus in ("docker0", "veth1a2b3c", "enp4s0", "wlan9"):
        with pytest.raises(SystemExit):
            lan.run("trust-current", "--interface", bogus)


# ================================================================ detección de interfaces

def test_only_physical_ethernet_and_wifi_are_candidates(lan):
    lan.set(eth={}, wifi={})
    networks = lan.fw.detect_networks()
    assert [(n.iface, n.medium, n.subnet, n.gateway, n.gw_mac) for n in networks] == [
        (ETH, "wired", LAN_A, "192.168.10.1", GW_A), (WIFI, "wifi", LAN_B, "192.168.48.1", GW_B)]
    assert networks[1].ssid == "OficinaADQ" and networks[0].ssid is None


def test_interface_names_do_not_matter(lan):
    lan.set(extra=[{"name": "eth1", "kind": "wired", "ip": "192.168.30.2/24", "gw": "192.168.30.1",
                    "gw_mac": OTHER_GW},
                   {"name": "wlan0", "kind": "wifi", "ip": "192.168.31.2/24", "gw": "192.168.31.1",
                    "gw_mac": GW_B, "ssid": "Oficina2"}])
    assert [(n.iface, n.medium) for n in lan.fw.detect_networks()] == [("eth1", "wired"), ("wlan0", "wifi")]


# ================================================================ UFW y estado

def test_legacy_ssid_or_interface_entries_are_ignored(lan):
    conf = Path(os.environ["SO_LAN_FIREWALL_CONF"])
    conf.parent.mkdir(parents=True, exist_ok=True)
    conf.write_text(json.dumps({"trusted_networks": [{"id": "wifi:OficinaADQ"}, {"id": f"wired:{ETH}"}]}))
    assert lan.run("apply", "--require-rules") == 3
    assert lan.rules() == []


def test_legacy_single_network_state_is_converted(lan):
    lan.run("trust-current")
    state = Path(os.environ["SO_LAN_FIREWALL_STATE"])
    state.write_text(json.dumps({"rules": [{"iface": ETH, "subnet": LAN_A, "port": "8080", "proto": "tcp"}],
                                 "network": {"iface": ETH, "subnet": LAN_A, "gateway": "192.168.10.1"}}))
    lan.set(eth={"gw_mac": None})
    lan.run("apply")
    assert lan.rules() == [web(ETH, LAN_A)]  # HOLD sigue funcionando tras actualizar


def test_legacy_subnet_rules_are_replaced_and_foreign_rules_untouched(lan):
    legacy = {"display": [f"8080/tcp on {ETH}", LAN_A], "comment": "Server Oficina LAN"}
    lan.ufw(rules=[SSH, legacy])
    lan.run("apply")  # sin red confiable: la regla legado fija a una subred se cierra
    assert lan.ufw()["rules"] == [SSH]
    lan.run("trust-current")
    assert SSH in lan.ufw()["rules"] and lan.rules() == [web(ETH, LAN_A)]


def test_unrecognised_or_duplicate_managed_rules_are_replaced(lan):
    lan.run("trust-current")
    manual = {"display": ["9999/tcp", "Anywhere"], "comment": "server-oficina-lan"}
    duplicate = {"args": ["in", "on", ETH, "from", LAN_A, "to", "any", "port", "8080", "proto", "tcp"],
                 "comment": "server-oficina-lan"}
    lan.ufw(rules=lan.ufw()["rules"] + [manual, duplicate])
    assert lan.run("apply", "--require-rules") == 0
    assert lan.rules() == [web(ETH, LAN_A)] and len(lan.ufw()["rules"]) == 1


def test_reapply_is_idempotent_and_survives_lost_state(lan):
    trust_both(lan)
    lan.run("apply")
    assert lan.ops() == []
    Path(os.environ["SO_LAN_FIREWALL_STATE"]).unlink()
    lan.run("apply")
    assert lan.ops() == [] and len(lan.rules()) == 2


def test_inactive_ufw_is_never_modified_and_not_ready(lan):
    lan.ufw(active=False)
    lan.run("trust-current")
    assert lan.run("apply", "--require-rules") == 3
    assert lan.ufw()["rules"] == []


def test_failed_rule_application_is_reported_not_ready(lan):
    lan.ufw(fail_allow=True)
    with pytest.raises(Exception):
        lan.run("trust-current")


def test_status_is_read_only_and_verifies_in_place_rules(lan):
    trust_both(lan)
    lan.run("api", "on")
    lan.ops()
    report = lan.report("status")
    assert report["verified"] is True and report["api"]["objetivo"] == "0.0.0.0"
    assert lan.ops() == [] and lan.api_host() == "127.0.0.1"


@pytest.mark.parametrize("subnet,ok", [
    ("192.168.48.0/24", True), ("10.20.0.0/16", True), ("172.20.1.0/24", True),
    ("203.0.113.0/24", False), ("100.64.0.0/24", False), ("8.8.8.0/24", False),
    ("169.254.0.0/16", False), ("0.0.0.0/0", False), ("172.32.0.0/24", False), (None, False),
])
def test_only_rfc1918_subnets_are_acceptable(lan, subnet, ok):
    assert lan.fw.subnet_is_acceptable(subnet) is ok


def test_parsers(lan):
    fw = lan.fw
    assert fw.parse_ssid("Connected to x\n\tSSID: \n\tfreq: 5180") is None
    assert fw.parse_ssid("Connected to x\n\tSSID: Oficina ADQ 5G\n\tfreq: 5180") == "Oficina ADQ 5G"
    assert fw.parse_neigh_mac("192.168.48.1 dev wlp2s0 lladdr AA:BB:CC:00:00:01 STALE") == "aa:bb:cc:00:00:01"
    assert fw.parse_neigh_mac("192.168.48.1 dev wlp2s0 FAILED") is None
    assert fw.parse_nmcli_active(f"lo:aaaa\n{WIFI}:{NM_WIFI}\n{ETH}:{NM_ETH}\n") == {
        "lo": "aaaa", WIFI: NM_WIFI, ETH: NM_ETH}
    assert fw.parse_default_routes(
        "default via 10.0.0.1 dev enp0s31f6 proto dhcp metric 100\n"
        "default via 192.168.48.1 dev wlp2s0 proto dhcp metric 600\n"
        "default via 10.0.0.254 dev enp0s31f6 proto static metric 20100\n") == {
        "enp0s31f6": "10.0.0.1", "wlp2s0": "192.168.48.1"}
    assert fw.parse_ipv4_addresses(
        "2: enp0s31f6    inet 192.168.10.23/24 brd 192.168.10.255 scope global dynamic noprefixroute enp0s31f6\\"
        "       valid_lft 86399sec preferred_lft 86399sec\n"
        "3: wlp2s0    inet 192.168.48.109/24 brd 192.168.48.255 scope global dynamic wlp2s0\\ valid_lft x\n") == {
        "enp0s31f6": ["192.168.10.23/24"], "wlp2s0": ["192.168.48.109/24"]}
    # Formato real de UFW 0.36.2 (verificado con ufw en un namespace de red).
    managed, legacy = fw.parse_ufw_numbered(
        "Status: active\n\n     To                         Action      From\n"
        "     --                         ------      ----\n"
        "[ 1] 8080/tcp on enp0s31f6      ALLOW IN    192.168.10.0/24            # server-oficina-lan\n"
        "[ 2] 22000/udp on wlp2s0        ALLOW IN    192.168.48.0/24            # server-oficina-lan\n"
        "[ 3] 22/tcp                     ALLOW IN    Anywhere                   # ssh\n"
        "[ 4] 8080/tcp on wlp2s0         ALLOW IN    192.168.48.0/24            # Server Oficina LAN\n"
        "[ 5] 22000/tcp on enx00e04c680001 ALLOW IN    172.20.100.0/22            # server-oficina-lan\n")
    assert managed == [(1, fw.Rule(ETH, LAN_A, "8080", "tcp")), (2, fw.Rule(WIFI, LAN_B, "22000", "udp")),
                       (5, fw.Rule("enx00e04c680001", "172.20.100.0/22", "22000", "tcp"))]
    assert legacy == [4]


# ================================================================ auditoría (descubrimiento y no-router)

def test_audit_avahi_announces_on_every_published_lan(lan):
    fw = lan.fw
    default = "[server]\nuse-ipv4=yes\nuse-ipv6=yes\n[reflector]\n#enable-reflector=no\n"
    ok = fw.audit_avahi([ETH, WIFI], default, "active", "server-oficina")
    assert ok["problemas"] == [] and ok["nombre"] == "server-oficina.local"
    bad = fw.audit_avahi([ETH, WIFI], "[server]\nallow-interfaces=enp0s31f6\n[reflector]\nenable-reflector=yes\n",
                         "inactive", "latitude")
    text = " ".join(bad["problemas"])
    assert "no está activo" in text and "reflector" in text and WIFI in text and "latitude.local" in text


def test_audit_forwarding_detects_router_behaviour(lan):
    fw = lan.fw
    nets = [fw.Network(ETH, subnet=LAN_A), fw.Network(WIFI, subnet=LAN_B)]
    assert fw.audit_forwarding("0\n", "ACCEPT", "DROP", nets, "")["problemas"] == []
    # Docker activa ip_forward; con política FORWARD DROP la Latitude no enruta entre LAN.
    assert fw.audit_forwarding("1\n", "DROP", "DROP", nets,
                               "-A POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE")["problemas"] == []
    bad = fw.audit_forwarding("1\n", "ACCEPT", "ACCEPT", nets,
                              f"-A POSTROUTING -s {LAN_A} -o {WIFI} -j MASQUERADE")["problemas"]
    assert len(bad) == 3


def test_audit_listeners(lan):
    fw = lan.fw
    listeners = fw.parse_listeners(
        "tcp   LISTEN 0 4096 0.0.0.0:8080 0.0.0.0:*\n"
        "tcp   LISTEN 0 4096 *:22000 *:*\n"
        "udp   UNCONN 0 0    *:22000 *:*\n"
        "udp   UNCONN 0 0    0.0.0.0:21027 0.0.0.0:*\n"
        "tcp   LISTEN 0 4096 127.0.0.1:8384 0.0.0.0:*\n")
    assert fw.audit_listeners(listeners, [ETH, WIFI], "0.0.0.0")["problemas"] == []
    assert fw.audit_listeners(listeners, [], "0.0.0.0")["problemas"] == [
        "la API escucha en 0.0.0.0 sin ninguna LAN confiable publicada"]
    only_one = fw.parse_listeners("tcp LISTEN 0 4096 192.168.10.23:22000 0.0.0.0:*\n")
    assert fw.audit_listeners(only_one, [ETH], "127.0.0.1")["problemas"]
