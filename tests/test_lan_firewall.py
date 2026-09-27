"""Reconciliador UFW: acceso LAN que sobrevive a cambios de router/DHCP sin IP fija."""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FAKE_UFW = r'''#!PYTHON
import json, os, sys
db = os.environ["FAKE_UFW_DB"]
state = json.load(open(db)) if os.path.exists(db) else {"active": True, "rules": []}
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
if "default" in sys.argv:
    print(f"default via {{n['gw']}} dev {{n['iface']}} proto dhcp metric 600")
else:
    print(f"{{n['subnet']}} proto kernel scope link src {{n['ip']}} metric 600")
''')
    write("iw", f'''#!{sys.executable}
import json
n = json.load(open({str(net)!r}))
print(f"Connected to aa:bb:cc:dd:ee:ff (on {{n['iface']}})\\n\\tSSID: {{n['ssid']}}\\n\\tfreq: 5180")
''')
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_UFW_DB", str(tmp_path / "ufw.json"))
    monkeypatch.setenv("SO_LAN_FIREWALL_CONF", str(tmp_path / "etc" / "lan-firewall.json"))
    monkeypatch.setenv("SO_LAN_FIREWALL_STATE", str(tmp_path / "var" / "state.json"))
    spec = importlib.util.spec_from_file_location("lan_firewall", ROOT / "scripts" / "lan_firewall.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "lan_firewall", module)
    spec.loader.exec_module(module)

    class Lab:
        fw = module

        @staticmethod
        def network(**values):
            net.write_text(json.dumps({"iface": "wlan0", "gw": "192.168.48.1", "ip": "192.168.48.109",
                                       "subnet": "192.168.48.0/24", "ssid": "OficinaADQ", **values}))

        @staticmethod
        def ufw(**state):
            db = Path(os.environ["FAKE_UFW_DB"])
            current = json.loads(db.read_text()) if db.exists() else {"active": True, "rules": []}
            if state:
                current.update(state)
                db.write_text(json.dumps(current))
            return current

        @staticmethod
        def run(*args):
            assert module.main(list(args)) == 0

    Lab.network()
    return Lab


def _specs(lan) -> list[str]:
    return [r["spec"] for r in lan.ufw()["rules"]]


def test_first_install_trusts_current_network_like_the_legacy_rule(lan):
    lan.run("apply", "--trust-current-if-empty")
    assert _specs(lan) == ["in on wlan0 from 192.168.48.0/24 to any port 8080 proto tcp"]


def test_same_wifi_new_subnet_is_followed_without_manual_edits(lan):
    """Gate 24: mismo SSID, router nuevo con otra subred DHCP."""
    lan.run("apply", "--trust-current-if-empty")
    lan.network(gw="10.20.0.1", ip="10.20.0.57", subnet="10.20.0.0/24")
    lan.run("apply")
    assert _specs(lan) == ["in on wlan0 from 10.20.0.0/24 to any port 8080 proto tcp"]


def test_untrusted_network_gets_no_rules_until_explicit_trust(lan):
    lan.run("apply", "--trust-current-if-empty")
    lan.network(ssid="Hotel-Invitados", gw="192.168.1.1", ip="192.168.1.30", subnet="192.168.1.0/24")
    lan.run("apply")
    assert _specs(lan) == []
    lan.run("trust-current")
    assert _specs(lan) == ["in on wlan0 from 192.168.1.0/24 to any port 8080 proto tcp"]


def test_public_subnet_is_never_opened_even_if_trusted(lan):
    lan.network(subnet="203.0.113.0/24", ip="203.0.113.9", gw="203.0.113.1")
    with pytest.raises(SystemExit):
        lan.run("trust-current")
    lan.run("apply")
    assert _specs(lan) == []


def test_optional_syncthing_and_mdns_ports_stay_on_the_lan(lan):
    lan.run("apply", "--trust-current-if-empty")
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
    lan.run("apply", "--trust-current-if-empty")
    rules = lan.ufw()["rules"]
    assert {"spec": "22/tcp ALLOW IN Anywhere", "comment": "ssh"} in rules
    assert not any(r["comment"] == "Server Oficina LAN" for r in rules)
    assert sum(r["comment"] == "server-oficina-lan" for r in rules) == 1


def test_reapply_is_idempotent_and_survives_lost_state(lan):
    lan.run("apply", "--trust-current-if-empty")
    lan.run("apply")
    assert len(_specs(lan)) == 1
    Path(os.environ["SO_LAN_FIREWALL_STATE"]).unlink()
    lan.run("apply")
    assert len(_specs(lan)) == 1


def test_inactive_ufw_is_never_modified(lan):
    lan.ufw(active=False)
    lan.run("apply", "--trust-current-if-empty")
    assert lan.ufw()["rules"] == []


def test_wifi_without_detectable_ssid_is_not_trusted_blindly(lan):
    lan.network(ssid="")
    with pytest.raises(SystemExit):
        lan.run("trust-current")


@pytest.mark.parametrize("subnet,ok", [
    ("192.168.48.0/24", True), ("10.20.0.0/16", True), ("172.20.1.0/24", True),
    ("203.0.113.0/24", False), ("100.64.0.0/24", False), ("8.8.8.0/24", False),
    ("169.254.0.0/16", False), ("0.0.0.0/0", False), ("172.32.0.0/24", False), (None, False),
])
def test_only_rfc1918_subnets_are_acceptable(lan, subnet, ok):
    assert lan.fw.subnet_is_acceptable(subnet) is ok


def test_ssid_parser_does_not_read_the_next_line(lan):
    assert lan.fw.parse_ssid("Connected to x\n\tSSID: \n\tfreq: 5180") is None
    assert lan.fw.parse_ssid("Connected to x\n\tSSID: Oficina ADQ 5G\n\tfreq: 5180") == "Oficina ADQ 5G"
