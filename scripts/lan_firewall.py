#!/usr/bin/env python3
"""Reconciliador UFW de Server Oficina: acceso LAN portable sin IP fija.

Problema: la regla histórica fijaba la subred vigente al instalar
(``from 192.168.48.0/24``). Al cambiar de rango DHCP, UFW bloqueaba Server
Oficina y había que reconfigurar a mano (equivalente a una IP hardcodeada).

Identidad de red (qué se confía)
--------------------------------
Ni el SSID ni el nombre de la interfaz identifican una red: otra Wi-Fi puede
usar el mismo SSID y ``eth0`` puede conectarse sucesivamente a LANs distintas.
La identidad se compone de:

* ``gw_mac`` — MAC del gateway por defecto (el router concreto). **Obligatoria.**
* ``nm`` — UUID del perfil de NetworkManager activo en la interfaz, si
  NetworkManager la gestiona.
* ``ssid`` — en Wi-Fi.
* ``medium`` — ``wifi`` o ``wired``.

Una red confiable coincide sólo si **todos** los componentes guardados al
confiar coinciden con los actuales. Consecuencias:

* nueva IP por DHCP en la misma red: misma identidad, nada que hacer;
* el mismo router cambia su rango DHCP: misma identidad, las reglas siguen la
  nueva subred automáticamente;
* mismo SSID o misma ``eth0`` en otra red: otro gateway → **no confiable**;
* router reemplazado: otro gateway → exige ``trust-current`` (decisión explícita
  del operador; no se edita ninguna IP). Es el compromiso asumido entre
  portabilidad y seguridad.

Si la identidad no puede leerse temporalmente (ARP del gateway vacío,
NetworkManager reiniciándose) las reglas ya aplicadas se **mantienen** sólo si
interfaz, subred y gateway siguen iguales, y como máximo
``SO_LAN_FIREWALL_HOLD_SECONDS`` (600 s por defecto); después se cierran.

Siempre: sólo subredes RFC1918, sólo en la interfaz por defecto, nunca
``allow from anywhere``, nunca se tocan reglas ajenas (SSH, etc.). Las reglas
propias se reconocen por su comentario.

Uso (root):

    lan_firewall.py status
    lan_firewall.py apply [--require-rules]
    lan_firewall.py trust-current
    lan_firewall.py enable syncthing|mdns   /   disable syncthing|mdns

``apply --require-rules`` sale con código 3 si no quedaron reglas verificadas
para una red confiable (lo usa la instalación para decidir si publica en LAN).

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
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

CONF = Path(os.environ.get("SO_LAN_FIREWALL_CONF", "/etc/server-oficina/lan-firewall.json"))
STATE = Path(os.environ.get("SO_LAN_FIREWALL_STATE", "/var/lib/server-oficina/lan-firewall-state.json"))
HOLD_SECONDS = int(os.environ.get("SO_LAN_FIREWALL_HOLD_SECONDS", "600"))
COMMENT = "server-oficina-lan"
BASE_PORTS = [("8080", "tcp")]
OPTIONAL_PORTS = {
    "syncthing": [("22000", "tcp"), ("22000", "udp"), ("21027", "udp")],
    "mdns": [("5353", "udp")],
}
#: Comentarios de reglas creadas por versiones anteriores fijando una subred.
LEGACY_COMMENTS = {"Server Oficina LAN", "Syncthing LAN", "Syncthing LAN QUIC", "Syncthing descubrimiento local"}
#: Sólo LAN privadas RFC1918. ``ipaddress.is_private`` también acepta rangos de
#: documentación (203.0.113.0/24...) y CGNAT: no sirve como criterio de seguridad.
RFC1918 = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
_MAC = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


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
    gateway: str | None = None
    medium: str | None = None
    ssid: str | None = None
    gw_mac: str | None = None
    nm_uuid: str | None = None
    #: "ok" (perfil activo), "unmanaged", "absent" (sin NetworkManager) o "error".
    nm_state: str = "absent"

    def components(self) -> dict[str, str] | None:
        """Identidad completa o ``None`` si falta información imprescindible."""
        if not self.iface or not self.gw_mac or self.nm_state == "error":
            return None
        if self.medium == "wifi" and not self.ssid:
            return None
        found = {"medium": self.medium or "wired", "gw_mac": self.gw_mac}
        if self.ssid:
            found["ssid"] = self.ssid
        if self.nm_uuid:
            found["nm"] = self.nm_uuid
        return found

    @property
    def identity(self) -> str | None:
        found = self.components()
        return canonical(found) if found else None


def canonical(components: dict[str, str]) -> str:
    return "|".join(f"{k}={components[k]}" for k in ("medium", "ssid", "gw_mac", "nm") if k in components)


def run(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def parse_default_route(route_output: str) -> tuple[str | None, str | None]:
    for line in route_output.splitlines():
        if not line.startswith("default"):
            continue
        dev = re.search(r"\bdev\s+(\S+)", line)
        via = re.search(r"\bvia\s+(\S+)", line)
        if dev:
            return dev.group(1), via.group(1) if via else None
    return None, None


def parse_default_iface(route_output: str) -> str | None:
    return parse_default_route(route_output)[0]


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


def parse_neigh_mac(neigh_output: str) -> str | None:
    match = re.search(r"\blladdr\s+([0-9a-fA-F:]{17})\b", neigh_output)
    mac = match.group(1).lower() if match else None
    return mac if mac and _MAC.match(mac) and mac != "00:00:00:00:00:00" else None


def parse_nmcli_active(output: str, iface: str) -> str | None:
    """``nmcli -t -f DEVICE,UUID connection show --active`` → UUID del perfil de ``iface``."""
    for line in output.splitlines():
        fields = re.split(r"(?<!\\):", line)
        if len(fields) >= 2 and fields[0] == iface and fields[1]:
            return fields[1]
    return None


def _gateway_mac(iface: str, gateway: str | None) -> str | None:
    if not gateway:
        return None
    try:
        mac = parse_neigh_mac(run("ip", "-4", "neigh", "show", gateway, "dev", iface))
        if mac:
            return mac
        # Poblar la caché ARP (el gateway se usa constantemente; esto es raro).
        subprocess.run(["ping", "-c", "1", "-W", "1", "-I", iface, gateway],
                       capture_output=True, timeout=5, check=False)
        return parse_neigh_mac(run("ip", "-4", "neigh", "show", gateway, "dev", iface))
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def _nm_profile(iface: str) -> tuple[str | None, str]:
    try:
        result = subprocess.run(["nmcli", "-t", "-f", "DEVICE,UUID", "connection", "show", "--active"],
                                capture_output=True, text=True, timeout=10, check=False)
    except FileNotFoundError:
        return None, "absent"
    except (OSError, subprocess.TimeoutExpired):
        return None, "error"
    if result.returncode == 8:  # "NetworkManager is not running"
        return None, "absent"
    if result.returncode != 0:
        return None, "error"
    uuid = parse_nmcli_active(result.stdout, iface)
    return uuid, "ok" if uuid else "unmanaged"


def detect_network() -> Network:
    iface, gateway = parse_default_route(run("ip", "-4", "route", "show", "default"))
    if not iface:
        return Network(None, None)
    subnet = parse_link_subnet(run("ip", "-4", "route", "show", "dev", iface, "scope", "link"))
    wireless = Path(f"/sys/class/net/{iface}/wireless").exists() or iface.startswith(("wl", "wlan"))
    ssid = None
    if wireless:
        try:
            ssid = parse_ssid(run("iw", "dev", iface, "link"))
        except (OSError, subprocess.CalledProcessError):
            ssid = None
    nm_uuid, nm_state = _nm_profile(iface)
    return Network(iface, subnet, gateway, "wifi" if wireless else "wired", ssid,
                   _gateway_mac(iface, gateway), nm_uuid, nm_state)


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


def trusted_entries(conf: dict) -> list[dict]:
    """Entradas válidas. Las de formato antiguo (``wifi:SSID``/``wired:iface``) se ignoran."""
    return [n for n in conf.get("trusted_networks", [])
            if isinstance(n.get("components"), dict) and n["components"].get("gw_mac")]


def matching_entry(conf: dict, network: Network) -> dict | None:
    current = network.components()
    if not current:
        return None
    for entry in trusted_entries(conf):
        if all(current.get(k) == v for k, v in entry["components"].items()):
            return entry
    return None


def load_state() -> dict:
    if not STATE.exists():
        return {}
    return json.loads(STATE.read_text(encoding="utf-8"))


def _rules(state: dict) -> set[Rule]:
    return {Rule(**r) for r in state.get("rules", [])}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def desired_rules(conf: dict, network: Network, state: dict | None = None) -> tuple[set[Rule], str, bool]:
    """(reglas deseadas, motivo, hold). ``hold`` = mantener reglas por pérdida temporal de identidad."""
    state = state or {}
    if not network.iface or not network.subnet:
        return set(), "sin red IPv4 por defecto", False
    if not subnet_is_acceptable(network.subnet):
        return set(), f"subred {network.subnet} no es LAN privada RFC1918: no se abre nada", False
    if network.components() is None:
        applied = _rules(state)
        previous = state.get("network") or {}
        same_place = (previous.get("iface"), previous.get("subnet"), previous.get("gateway")) == (
            network.iface, network.subnet, network.gateway)
        since = state.get("hold_since")
        elapsed = (_now() - datetime.fromisoformat(since)).total_seconds() if since else 0.0
        if applied and same_place and elapsed < HOLD_SECONDS:
            return applied, ("identidad de red temporalmente no disponible; se mantienen las reglas "
                             f"de {network.iface} {network.subnet} (HOLD {int(elapsed)}s/{HOLD_SECONDS}s)"), True
        return set(), f"no se pudo identificar la red de {network.iface} (gateway/SSID/NetworkManager)", False
    if matching_entry(conf, network) is None:
        return set(), f"red {network.identity} no confiable: ejecutar trust-current si corresponde", False
    ports = list(BASE_PORTS)
    for option, extra in OPTIONAL_PORTS.items():
        if conf.get(option):
            ports.extend(extra)
    return ({Rule(network.iface, network.subnet, p, proto) for p, proto in ports},
            f"red confiable {network.identity}", False)


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

    No depende del archivo de estado para limpiar: las reglas propias se
    reconocen por su comentario, así que un estado perdido nunca deja huérfanas.
    """
    state = load_state()
    desired, reason, hold = desired_rules(conf, network, state)
    applied = _rules(state)
    report = {
        "network": asdict(network), "identity": network.identity, "reason": reason, "hold": hold,
        "rules": [r.__dict__ for r in sorted(desired)],
        "added": [r.__dict__ for r in sorted(desired - applied)],
        "removed": [r.__dict__ for r in sorted(applied - desired)],
        "legacy_removed": 0, "changed": False, "verified": False,
    }
    if dry_run:
        return report
    numbered = run("ufw", "status", "numbered")
    managed = rule_numbers(numbered, {COMMENT})
    legacy = rule_numbers(numbered, LEGACY_COMMENTS)
    if not (desired == applied and len(managed) == len(desired) and not legacy):
        for number in sorted(managed + legacy, reverse=True):
            run("ufw", "--force", "delete", str(number))
        for rule in sorted(desired):
            run("ufw", "allow", *rule.ufw_args(), "comment", COMMENT)
        report.update(legacy_removed=len(legacy), changed=True)
    new_state = {"rules": [r.__dict__ for r in sorted(desired)], "network": asdict(network),
                 "updated_at": _now().isoformat()}
    if hold:
        # En HOLD se conserva la red con identidad conocida para seguir comparando.
        new_state["network"] = state.get("network", asdict(network))
        new_state["hold_since"] = state.get("hold_since") or _now().isoformat()
    save_json(STATE, new_state)
    report["verified"] = len(rule_numbers(run("ufw", "status", "numbered"), {COMMENT})) == len(desired)
    return report


def trust(conf: dict, network: Network) -> dict:
    components = network.components()
    if not components:
        raise SystemExit("No se pudo identificar la red actual (MAC del gateway, SSID o perfil de "
                         "NetworkManager); no se confía a ciegas.")
    if not subnet_is_acceptable(network.subnet):
        raise SystemExit(f"La subred {network.subnet} no es LAN privada RFC1918; no se confía.")
    if matching_entry(conf, network) is None:
        conf.setdefault("trusted_networks", []).append({
            "id": canonical(components), "components": components,
            "added_at": _now().isoformat(), "first_subnet": network.subnet,
        })
        save_json(CONF, conf)
    return conf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    ap = sub.add_parser("apply")
    ap.add_argument("--require-rules", action="store_true",
                    help="código 3 si no quedan reglas verificadas para una red confiable")
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
    if args.cmd == "trust-current":
        conf = trust(conf, network)
    active = ufw_active()
    report = apply(conf, network, dry_run=args.cmd == "status" or not active)
    report["ufw"] = "activo" if active else "inactivo: no se modificó nada"
    legacy_entries = len(conf.get("trusted_networks", [])) - len(trusted_entries(conf))
    if legacy_entries:
        report["entradas_legado_ignoradas"] = legacy_entries
    print("LAN_FIREWALL " + json.dumps(report, ensure_ascii=False))
    if args.cmd == "apply" and args.require_rules:
        ready = active and report["rules"] and report["verified"] and not report["hold"]
        return 0 if ready else 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
