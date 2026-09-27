"""Reconciliador UFW: acceso LAN que sobrevive a DHCP sin confiar en SSID ni interfaz.

La identidad de red es MAC del gateway + perfil de NetworkManager (si existe) +
SSID en Wi-Fi. Se simulan ``ip``, ``iw``, ``nmcli``, ``ping`` y ``ufw``.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OFFICE_GW = "aa:bb:cc:00:00:01"
OTHER_GW = "aa:bb:cc:99:99:99"
NM_OFFICE = "11111111-2222-3333-4444-555555555555"

FAKE_UFW = r'''#!PYTHON
import json, os, sys
db = os.environ["FAKE_UFW_DB"]
state = json.load(open(db)) if os.path.exists(db) else {"active": True, "rules": [], "fail_allow": False}
args = sys.argv[1:]
def save(): json.dump(state, open(db, "w"))
if args[:2] == ["status", "numbered"]:
    print("Status: active" if state["active"] else "Status: inactive")
    for i, r in enumerate(state["rules"], 1):
        print(f"[{i:2d}] {r['spec']}   # {r['comment']}")
elif args == ["status"]:
    print("Status: active" if state["active"] else "Status: inactive")
elif args[:2] == ["--force", "delete"]:
    del state["rules"][int(args[2]) - 1]; save()
elif args[0] == "allow":
    if state.get("fail_allow"):
        print("ERROR: simulated failure", file=sys.stderr); sys.exit(1)
    spec, comment = " ".join(args[1:args.index("comment")]), args[args.index("comment") + 1]
    state["rules"].append({"spec": spec, "comment": comment}); save()
else:
    sys.exit(2)
'''


@pytest.fixture()
def lan(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    net = tmp_path / "net.json"

    def write(name: str, body: str):
        path = bin_dir / name
        path.write_text(body.replace("#!PYTHON", f"#!{sys.executable}"))
        path.chmod(0o755)

    write("ufw", FAKE_UFW)
    write("ip", f'''#!{sys.executable}
import json, sys
n = json.load(open({str(net)!r}))
args = sys.argv[1:]
if "neigh" in args:
    if n.get("gw_mac"):
        print(f"{{n['gw']}} lladdr {{n['gw_mac']}} REACHABLE")
    else:
        print(f"{{n['gw']}}  INCOMPLETE")
elif "default" in args:
    print(f"default via {{n['gw']}} dev {{n['iface']}} proto dhcp metric 600")
else:
    print(f"{{n['subnet']}} proto kernel scope link src {{n['ip']}} metric 600")
''')
    write("iw", f'''#!{sys.executable}
import json
n = json.load(open({str(net)!r}))
print(f"Connected to 02:00:00:00:00:01 (on {{n['iface']}})\\n\\tSSID: {{n.get('ssid','')}}\\n\\tfreq: 5180")
''')
    write("nmcli", f'''#!{sys.executable}
import json, sys
n = json.load(open({str(net)!r}))
mode = n.get("nm", "absent")
if mode == "absent":
    print("Error: NetworkManager is not running.", file=sys.stderr); sys.exit(8)
if mode == "error":
    print("Error: timeout", file=sys.stderr); sys.exit(1)
if mode == "ok":
    print(f"{{n['iface']}}:{{n['nm_uuid']}}")
''')
    write("ping", "#!/bin/sh\nexit 0\n")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_UFW_DB", str(tmp_path / "ufw.json"))
    monkeypatch.setenv("SO_LAN_FIREWALL_CONF", str(tmp_path / "etc" / "lan-firewall.json"))
    monkeypatch.setenv("SO_LAN_FIREWALL_STATE", str(tmp_path / "var" / "state.json"))

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
        def network(**values):
            base = {"iface": "wlan0", "gw": "192.168.48.1", "ip": "192.168.48.109",
                    "subnet": "192.168.48.0/24", "ssid": "OficinaADQ", "gw_mac": OFFICE_GW,
                    "nm": "absent"}
            net.write_text(json.dumps({**base, **values}))

        @staticmethod
        def ufw(**state):
            db = Path(os.environ["FAKE_UFW_DB"])
            current = json.loads(db.read_text()) if db.exists() else {"active": True, "rules": [], "fail_allow": False}
            if state:
                current.update(state)
                db.write_text(json.dumps(current))
            return current

        @staticmethod
        def run(*args) -> int:
            return Lab.fw.main(list(args))

    Lab.network()
    return Lab


def _specs(lan) -> list[str]:
    return [r["spec"] for r in lan.ufw()["rules"] if r["comment"] == "server-oficina-lan"]


OFFICE_RULE = "in on wlan0 from 192.168.48.0/24 to any port 8080 proto tcp"


# 1 · misma red, nueva IP (DHCP)
def test_same_network_new_ip_keeps_access_without_intervention(lan):
    assert lan.run("trust-current") == 0
    assert _specs(lan) == [OFFICE_RULE]
    lan.network(ip="192.168.48.201")
    assert lan.run("apply", "--require-rules") == 0
    assert _specs(lan) == [OFFICE_RULE]


# 2 · misma identidad confiable (mismo router y perfil) + nueva subred
def test_same_trusted_identity_new_subnet_follows_automatically(lan):
    lan.network(nm="ok", nm_uuid=NM_OFFICE)
    lan.run("trust-current")
    lan.network(nm="ok", nm_uuid=NM_OFFICE, gw="10.20.0.1", ip="10.20.0.57", subnet="10.20.0.0/24")
    assert lan.run("apply", "--require-rules") == 0
    assert _specs(lan) == ["in on wlan0 from 10.20.0.0/24 to any port 8080 proto tcp"]


# 3 · mismo SSID, red distinta (otro router)
def test_same_ssid_different_network_is_not_trusted(lan):
    lan.run("trust-current")
    lan.network(gw_mac=OTHER_GW)
    assert lan.run("apply", "--require-rules") == 3
    assert _specs(lan) == []


# 4 · misma interfaz Ethernet, red distinta
def test_same_ethernet_interface_different_network_is_not_trusted(lan):
    lan.network(iface="eth0", ssid=None)
    lan.run("trust-current")
    assert _specs(lan) == ["in on eth0 from 192.168.48.0/24 to any port 8080 proto tcp"]
    lan.network(iface="eth0", ssid=None, gw_mac=OTHER_GW)
    assert lan.run("apply", "--require-rules") == 3
    assert _specs(lan) == []


def test_same_nm_profile_on_another_router_is_not_trusted(lan):
    """Un perfil 'Wired connection 1' se activa en cualquier LAN: el UUID solo no basta."""
    lan.network(iface="eth0", ssid=None, nm="ok", nm_uuid=NM_OFFICE)
    lan.run("trust-current")
    lan.network(iface="eth0", ssid=None, nm="ok", nm_uuid=NM_OFFICE, gw_mac=OTHER_GW)
    assert lan.run("apply", "--require-rules") == 3
    assert _specs(lan) == []


def test_same_router_but_other_nm_profile_is_not_trusted(lan):
    lan.network(nm="ok", nm_uuid=NM_OFFICE)
    lan.run("trust-current")
    lan.network(nm="ok", nm_uuid="99999999-0000-0000-0000-000000000000")
    assert lan.run("apply", "--require-rules") == 3


# 5 · red nueva no confiable
def test_new_network_gets_nothing_until_explicit_trust(lan):
    lan.run("trust-current")
    lan.network(ssid="Hotel-Invitados", gw="192.168.1.1", ip="192.168.1.30",
                subnet="192.168.1.0/24", gw_mac=OTHER_GW)
    assert lan.run("apply", "--require-rules") == 3
    assert _specs(lan) == []
    assert lan.run("trust-current") == 0
    assert _specs(lan) == ["in on wlan0 from 192.168.1.0/24 to any port 8080 proto tcp"]


def test_first_apply_never_trusts_implicitly(lan):
    assert lan.run("apply", "--require-rules") == 3
    assert _specs(lan) == []


# 6 · red pública
@pytest.mark.parametrize("subnet,ip,gw", [
    ("203.0.113.0/24", "203.0.113.9", "203.0.113.1"),
    ("100.64.0.0/24", "100.64.0.9", "100.64.0.1"),
    ("8.8.8.0/24", "8.8.8.9", "8.8.8.1"),
])
def test_public_network_is_never_opened(lan, subnet, ip, gw):
    lan.network(subnet=subnet, ip=ip, gw=gw)
    with pytest.raises(SystemExit):
        lan.run("trust-current")
    assert lan.run("apply", "--require-rules") == 3
    assert _specs(lan) == []


# 7 · pérdida temporal de la identidad
def test_temporary_identity_loss_holds_rules_on_same_place_then_closes(lan):
    lan.run("trust-current")
    lan.network(gw_mac=None)  # ARP del gateway vacío
    assert lan.run("apply") == 0
    assert _specs(lan) == [OFFICE_RULE]
    assert lan.run("apply", "--require-rules") == 3  # en HOLD no se declara lista
    lan.reload(hold_seconds=0)  # vence el plazo
    lan.run("apply")
    assert _specs(lan) == []
    lan.network()  # la identidad vuelve
    lan.run("apply")
    assert _specs(lan) == [OFFICE_RULE]


def test_identity_loss_with_changed_subnet_closes_immediately(lan):
    lan.run("trust-current")
    lan.network(gw_mac=None, gw="10.9.0.1", ip="10.9.0.5", subnet="10.9.0.0/24")
    lan.run("apply")
    assert _specs(lan) == []


def test_networkmanager_error_is_identity_loss_not_new_network(lan):
    lan.network(nm="ok", nm_uuid=NM_OFFICE)
    lan.run("trust-current")
    lan.network(nm="error")
    lan.run("apply")
    assert _specs(lan) == [OFFICE_RULE]


def test_wifi_without_ssid_or_gateway_is_never_trusted_blindly(lan):
    lan.network(ssid="")
    with pytest.raises(SystemExit):
        lan.run("trust-current")
    lan.network(gw_mac=None)
    with pytest.raises(SystemExit):
        lan.run("trust-current")


def test_legacy_ssid_or_interface_entries_are_ignored(lan):
    conf = Path(os.environ["SO_LAN_FIREWALL_CONF"])
    conf.parent.mkdir(parents=True)
    conf.write_text(json.dumps({"trusted_networks": [{"id": "wifi:OficinaADQ"}, {"id": "wired:eth0"}]}))
    lan.fw.CONF = conf
    assert lan.run("apply", "--require-rules") == 3
    assert _specs(lan) == []


def test_optional_ports_stay_on_the_lan(lan):
    lan.run("trust-current")
    lan.run("enable", "syncthing")
    lan.run("enable", "mdns")
    specs = _specs(lan)
    assert len(specs) == 5
    assert all(" from 192.168.48.0/24 " in s and s.startswith("in on wlan0 ") for s in specs)
    assert not any("Anywhere" in s or "0.0.0.0/0" in s for s in specs)


def test_legacy_subnet_rules_are_replaced_and_foreign_rules_untouched(lan):
    lan.ufw(rules=[
        {"spec": "22/tcp ALLOW IN Anywhere", "comment": "ssh"},
        {"spec": "8080/tcp on wlan0 ALLOW IN 192.168.48.0/24", "comment": "Server Oficina LAN"},
    ])
    lan.run("apply")  # sin red confiable: la regla legado fija a una subred se cierra
    rules = lan.ufw()["rules"]
    assert rules == [{"spec": "22/tcp ALLOW IN Anywhere", "comment": "ssh"}]
    lan.run("trust-current")
    assert {"spec": "22/tcp ALLOW IN Anywhere", "comment": "ssh"} in lan.ufw()["rules"]
    assert _specs(lan) == [OFFICE_RULE]


def test_reapply_is_idempotent_and_survives_lost_state(lan):
    lan.run("trust-current")
    lan.run("apply")
    assert len(_specs(lan)) == 1
    Path(os.environ["SO_LAN_FIREWALL_STATE"]).unlink()
    lan.run("apply")
    assert len(_specs(lan)) == 1


def test_inactive_ufw_is_never_modified_and_not_ready(lan):
    lan.ufw(active=False)
    lan.run("trust-current")
    assert lan.run("apply", "--require-rules") == 3
    assert lan.ufw()["rules"] == []


def test_failed_rule_application_is_reported_not_ready(lan):
    lan.ufw(fail_allow=True)
    with pytest.raises(Exception):
        lan.run("trust-current")


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
    assert fw.parse_neigh_mac("192.168.48.1 dev wlan0 lladdr AA:BB:CC:00:00:01 STALE") == OFFICE_GW
    assert fw.parse_neigh_mac("192.168.48.1 dev wlan0 FAILED") is None
    assert fw.parse_nmcli_active(f"lo:aaaa\nwlan0:{NM_OFFICE}\n", "wlan0") == NM_OFFICE
    assert fw.parse_default_route("default via 10.0.0.1 dev eth0 proto dhcp") == ("eth0", "10.0.0.1")
