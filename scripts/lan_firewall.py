#!/usr/bin/env python3
"""Reconciliador UFW de Server Oficina: acceso LAN portable sin IP fija.

Problema: la regla histórica fijaba la subred vigente al instalar
(``from 192.168.48.0/24``). Al cambiar de router o de rango DHCP, UFW bloqueaba
Server Oficina y había que reconfigurar a mano (equivalente a una IP
hardcodeada).

Modelo:

* La **confianza es por red**, no por IP: el SSID de la Wi-Fi (``wifi:<SSID>``)
  o la interfaz cableada (``wired:<iface>``). Se guarda en
  ``/etc/server-oficina/lan-firewall.json``.
* En cada cambio de red (dispatcher de NetworkManager y timer de respaldo) se
  recalcula la subred de la interfaz por defecto y se permiten los puertos
  **sólo desde esa subred, sólo en esa interfaz y sólo si es privada** (RFC1918).
* Una red no confiable no recibe ninguna regla: el acceso a una red nueva es una
  decisión explícita (``trust-current``), no una edición de IPs.
* Nunca ``allow from anywhere``; nunca se tocan reglas ajenas (SSH, etc.).

Uso (root):

    lan_firewall.py status
    lan_firewall.py apply [--trust-current-if-empty]
    lan_firewall.py trust-current
    lan_firewall.py enable syncthing|mdns   /   disable syncthing|mdns

Sólo usa la biblioteca estándar: se ejecuta con el python3 del sistema.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CONF = Path(os.environ.get("SO_LAN_FIREWALL_CONF", "/etc/server-oficina/lan-firewall.json"))
STATE = Path(os.environ.get("SO_LAN_FIREWALL_STATE", "/var/lib/server-oficina/lan-firewall-state.json"))
COMMENT = "server-oficina-lan"
BASE_PORTS = [("8080", "tcp")]
OPTIONAL_PORTS = {
    "syncthing": [("22000", "tcp"), ("22000", "udp"), ("21027", "udp")],
    "mdns": [("5353", "udp")],
}
#: Comentarios de reglas creadas por versiones anteriores fijando una subred.
LEGACY_COMMENTS = {"Server Oficina LAN", "Syncthing LAN", "Syncthing LAN QUIC", "Syncthing descubrimiento local"}


@dataclass(frozen=True, order=True)
class Rule:
    iface: str
    subnet: str
    port: str
    proto: str

    def ufw_args(self) -> list[str]:
        return ["in", "on", self.iface, "from", self.subnet, "to", "any", "port", self.port, "proto", self.proto]


@dataclass(frozen=True)
class Network:
    iface: str | None
    subnet: str | None
    identity: str | None


def run(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def parse_default_iface(route_output: str) -> str | None:
    for line in route_output.splitlines():
        match = re.search(r"\bdev\s+(\S+)", line)
        if line.startswith("default") and match:
            return match.group(1)
    return None


def parse_link_subnet(route_output: str) -> str | None:
    for line in route_output.splitlines():
        first = line.split()[0] if line.split() else ""
        if "/" in first:
            try:
                return str(ipaddress.ip_network(first, strict=False))
            except ValueError:
                continue
    return None


def parse_ssid(iw_output: str) -> str | None:
    match = re.search(r"^[ \t]*SSID:[ \t]*(\S.*?)[ \t]*$", iw_output, re.M)
    return match.group(1) if match else None


def detect_network() -> Network:
    iface = parse_default_iface(run("ip", "-4", "route", "show", "default"))
    if not iface:
        return Network(None, None, None)
    subnet = parse_link_subnet(run("ip", "-4", "route", "show", "dev", iface, "scope", "link"))
    wireless = Path(f"/sys/class/net/{iface}/wireless").exists() or iface.startswith(("wl", "wlan"))
    identity = None
    if wireless:
        try:
            ssid = parse_ssid(run("iw", "dev", iface, "link"))
        except (OSError, subprocess.CalledProcessError):
            ssid = None
        identity = f"wifi:{ssid}" if ssid else None
    else:
        identity = f"wired:{iface}"
    return Network(iface, subnet, identity)


#: Sólo LAN privadas RFC1918. ``ipaddress.is_private`` también acepta rangos de
#: documentación (203.0.113.0/24...) y CGNAT: no sirve como criterio de seguridad.
RFC1918 = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]


def subnet_is_acceptable(subnet: str | None) -> bool:
    if not subnet:
        return False
    try:
        net = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return False
    return net.version == 4 and any(net.subnet_of(block) for block in RFC1918)


def load_conf() -> dict:
    if CONF.exists():
        return json.loads(CONF.read_text(encoding="utf-8"))
    return {"trusted_networks": [], "syncthing": False, "mdns": False}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(temp, 0o640)
    os.replace(temp, path)


def desired_rules(conf: dict, network: Network) -> tuple[set[Rule], str]:
    trusted = {n["id"] for n in conf.get("trusted_networks", [])}
    if not network.iface or not network.subnet:
        return set(), "sin red IPv4 por defecto"
    if not network.identity:
        return set(), f"no se pudo identificar la red de {network.iface} (¿SSID?)"
    if network.identity not in trusted:
        return set(), f"red {network.identity} no confiable: ejecutar trust-current si corresponde"
    if not subnet_is_acceptable(network.subnet):
        return set(), f"subred {network.subnet} no es LAN privada: no se abre nada"
    ports = list(BASE_PORTS)
    for option, extra in OPTIONAL_PORTS.items():
        if conf.get(option):
            ports.extend(extra)
    return {Rule(network.iface, network.subnet, p, proto) for p, proto in ports}, f"red confiable {network.identity}"


def load_state() -> set[Rule]:
    if not STATE.exists():
        return set()
    return {Rule(**r) for r in json.loads(STATE.read_text(encoding="utf-8")).get("rules", [])}


def ufw_active() -> bool:
    try:
        return "Status: active" in run("ufw", "status")
    except (OSError, subprocess.CalledProcessError):
        return False


def rule_numbers(numbered_output: str, comments: set[str]) -> list[int]:
    """Números de regla (descendentes, para borrar sin renumerar) por comentario."""
    numbers = []
    for line in numbered_output.splitlines():
        match = re.match(r"^\[\s*(\d+)\]\s.*#\s*(.+?)\s*$", line)
        if match and match.group(2) in comments:
            numbers.append(int(match.group(1)))
    return sorted(numbers, reverse=True)


def apply(conf: dict, network: Network, *, dry_run: bool = False) -> dict:
    """Reconcilia: si algo difiere, borra las reglas propias y legado y recrea las deseadas.

    No depende del archivo de estado: las reglas propias se reconocen por su
    comentario, así que un estado perdido nunca deja reglas huérfanas.
    """
    desired, reason = desired_rules(conf, network)
    applied = load_state()
    report = {
        "network": network.__dict__, "reason": reason,
        "rules": [r.__dict__ for r in sorted(desired)],
        "added": [r.__dict__ for r in sorted(desired - applied)],
        "removed": [r.__dict__ for r in sorted(applied - desired)],
        "legacy_removed": 0, "changed": False,
    }
    if dry_run:
        return report
    numbered = run("ufw", "status", "numbered")
    managed = rule_numbers(numbered, {COMMENT})
    legacy = rule_numbers(numbered, LEGACY_COMMENTS)
    if desired == applied and len(managed) == len(desired) and not legacy:
        return report
    for number in sorted(managed + legacy, reverse=True):
        run("ufw", "--force", "delete", str(number))
    for rule in sorted(desired):
        run("ufw", "allow", *rule.ufw_args(), "comment", COMMENT)
    save_json(STATE, {"rules": [r.__dict__ for r in sorted(desired)],
                      "network": network.__dict__, "updated_at": datetime.now(timezone.utc).isoformat()})
    report.update(legacy_removed=len(legacy), changed=True)
    return report


def trust(conf: dict, network: Network) -> dict:
    if not network.identity:
        raise SystemExit("No se pudo identificar la red actual; no se confía a ciegas.")
    if not subnet_is_acceptable(network.subnet):
        raise SystemExit(f"La subred {network.subnet} no es LAN privada; no se confía.")
    ids = {n["id"] for n in conf.setdefault("trusted_networks", [])}
    if network.identity not in ids:
        conf["trusted_networks"].append({"id": network.identity, "added_at": datetime.now(timezone.utc).isoformat(),
                                         "first_subnet": network.subnet})
        save_json(CONF, conf)
    return conf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    ap = sub.add_parser("apply")
    ap.add_argument("--trust-current-if-empty", action="store_true")
    sub.add_parser("trust-current")
    for name in ("enable", "disable"):
        opt = sub.add_parser(name)
        opt.add_argument("option", choices=sorted(OPTIONAL_PORTS))
    args = parser.parse_args(argv)

    conf = load_conf()
    network = detect_network()
    if args.cmd in {"enable", "disable"}:
        conf[args.option] = args.cmd == "enable"
        save_json(CONF, conf)
    if args.cmd == "trust-current" or (
        args.cmd == "apply" and args.trust_current_if_empty and not conf.get("trusted_networks")
    ):
        conf = trust(conf, network)
    if args.cmd == "status" or not ufw_active():
        report = apply(conf, network, dry_run=True)
        report["ufw"] = "activo" if ufw_active() else "inactivo: no se modificó nada"
    else:
        report = apply(conf, network)
        report["ufw"] = "activo"
    print("LAN_FIREWALL " + json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
