#!/usr/bin/env python3
"""Reconciliador UFW de Server Oficina: acceso LAN multi-interfaz sin IP fija.

La Latitude puede estar conectada **a la vez** por Ethernet y por Wi-Fi, cada
interfaz a una LAN distinta de la oficina. Server Oficina se ofrece desde
**todas** las LAN confiables activas simultáneamente. La Latitude no enruta
entre ellas: no hay forwarding, bridge ni NAT; sólo ofrece sus propios servicios
en cada interfaz (``audit`` lo comprueba).

    LAN A ─── Ethernet ─┐
                        Latitude        (no: LAN A ← router → LAN B)
    LAN B ───── Wi-Fi ──┘

Interfaces candidatas
---------------------
NIC físicas (``/sys/class/net/<if>/device``) Ethernet o Wi-Fi (``wireless`` o
``phy80211``), en estado ``up``, no esclavas de un bridge, con una dirección
IPv4 global. El nombre no importa (``enp…``, ``wlp…``, ``eth0``…). Quedan fuera
loopback, Docker, bridges, veth, VPN y túneles.

Identidad de red (qué se confía) — independiente para cada LAN
--------------------------------------------------------------
Ni el SSID ni el nombre de la interfaz identifican una red: otra Wi-Fi puede
usar el mismo SSID y ``eth0`` puede conectarse a LANs distintas. Para cada
interfaz la identidad es:

* ``gw_mac`` — MAC del gateway de esa interfaz (el router concreto). **Obligatoria.**
* ``nm`` — UUID del perfil de NetworkManager activo en la interfaz, si lo hay.
* ``ssid`` — en Wi-Fi.
* ``medium`` — ``wifi`` o ``wired``.

``trusted_networks`` guarda una entrada por LAN confiada; una LAN activa es
confiable sólo si **todos** los componentes de alguna entrada coinciden con los
actuales. La subred y la interfaz no forman parte de la identidad: se leen en
cada ejecución. Consecuencias, para cada LAN por separado:

* nueva IP o nuevo rango DHCP en la misma red: las reglas siguen solas;
* mismo SSID u otra LAN en la misma interfaz: otro gateway → **no confiable**;
* router reemplazado: exige ``trust-current --interface <if>`` (decisión
  explícita; compromiso asumido entre portabilidad y seguridad);
* identidad ilegible un momento (ARP vacío, NetworkManager reiniciando): las
  reglas de **esa** interfaz se mantienen si su subred y gateway no cambian,
  como máximo ``SO_LAN_FIREWALL_HOLD_SECONDS`` (600 s); luego se cierran;
* interfaz caída: se retiran sólo sus reglas; las demás LAN no se tocan.

Reglas
------
Para cada LAN confiable activa, ``in on <interfaz> from <subred actual>``:
8080/tcp; con Syncthing 22000/tcp, 22000/udp y 21027/udp; con mDNS 5353/udp.
Sólo RFC1918, nunca ``allow from anywhere``, nunca se tocan reglas ajenas (SSH).
La reconciliación es **incremental**: se borran sólo las reglas propias que
sobran y se añaden las que faltan; un cambio en una LAN nunca interrumpe otra.

API (``--sync-api``, lo usa el servicio systemd)
-----------------------------------------------
Si el operador pidió publicar la API (``api on``, lo hace
``configurar-acceso-lan.sh``), ``SERVER_OFICINA_HOST`` vale ``0.0.0.0`` sólo
mientras UFW esté activo con entrada ``deny``/``reject`` y quede al menos una
LAN confiable con reglas verificadas; si no, ``127.0.0.1``. Un único listener
``0.0.0.0:8080`` basta: UFW aísla por interfaz y subred. La API sólo se
reinicia al cruzar entre "ninguna LAN" y "alguna LAN".

Uso (root):

    lan_firewall.py status
    lan_firewall.py apply [--require-rules] [--sync-api]
    lan_firewall.py trust-current [--interface IF]... [--sync-api]
    lan_firewall.py enable|disable syncthing|mdns
    lan_firewall.py api on|off
    lan_firewall.py audit

``trust-current`` sin ``--interface`` sólo actúa si hay exactamente una LAN
activa; con varias exige nombrar la interfaz (nunca se confía una LAN
desconocida por estar enchufada al mismo tiempo que otra).
``apply --require-rules`` sale con código 3 si no queda ninguna LAN confiable
con reglas verificadas. ``audit`` (sólo lectura) revisa descubrimiento local
(Avahi/mDNS), escucha de Syncthing y API, y que la Latitude no enrute.

Sólo usa la biblioteca estándar: se ejecuta con el python3 del sistema.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

CONF = Path(os.environ.get("SO_LAN_FIREWALL_CONF", "/etc/server-oficina/lan-firewall.json"))
STATE = Path(os.environ.get("SO_LAN_FIREWALL_STATE", "/var/lib/server-oficina/lan-firewall-state.json"))
SYSFS = Path(os.environ.get("SO_LAN_FIREWALL_SYSFS", "/sys/class/net"))
ENV_FILE = Path(os.environ.get("SO_ENV_FILE", "/etc/server-oficina/server-oficina.env"))
AVAHI_CONF = Path(os.environ.get("SO_AVAHI_CONF", "/etc/avahi/avahi-daemon.conf"))
UFW_BEFORE_RULES = Path(os.environ.get("SO_UFW_BEFORE_RULES", "/etc/ufw/before.rules"))
UFW_DEFAULTS = Path(os.environ.get("SO_UFW_DEFAULTS", "/etc/default/ufw"))
LOCK = Path(os.environ.get("SO_LAN_FIREWALL_LOCK", "/run/server-oficina-lan-firewall.lock"))
HOLD_SECONDS = int(os.environ.get("SO_LAN_FIREWALL_HOLD_SECONDS", "600"))
HOSTNAME = "server-oficina"
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
#: ``ufw status numbered``: ``[ 1] 8080/tcp on enp0s31f6   ALLOW IN   192.168.10.0/24   # server-oficina-lan``
_UFW_RULE = re.compile(r"^\[\s*(\d+)\]\s+(\d+)/(tcp|udp)\s+on\s+(\S+)\s+ALLOW IN\s+(\S+)\s+#\s*(.+?)\s*$")
_UFW_COMMENT = re.compile(r"^\[\s*(\d+)\]\s.*#\s*(.+?)\s*$")

TRUSTED, HOLD, UNTRUSTED, UNIDENTIFIED, NOT_PRIVATE = (
    "confiable", "hold", "no_confiable", "sin_identidad", "no_rfc1918")


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
    """Una LAN activa vista desde una interfaz de la Latitude."""

    iface: str
    address: str | None = None
    subnet: str | None = None
    gateway: str | None = None
    medium: str = "wired"
    ssid: str | None = None
    gw_mac: str | None = None
    nm_uuid: str | None = None
    #: "ok" (perfil activo), "unmanaged", "absent" (sin NetworkManager) o "error".
    nm_state: str = "absent"

    def components(self) -> dict[str, str] | None:
        """Identidad completa o ``None`` si falta información imprescindible."""
        if not self.gw_mac or self.nm_state == "error":
            return None
        if self.medium == "wifi" and not self.ssid:
            return None
        found = {"medium": self.medium, "gw_mac": self.gw_mac}
        if self.ssid:
            found["ssid"] = self.ssid
        if self.nm_uuid:
            found["nm"] = self.nm_uuid
        return found

    @property
    def identity(self) -> str | None:
        found = self.components()
        return canonical(found) if found else None


@dataclass
class Decision:
    network: Network
    status: str
    reason: str
    rules: set[Rule] = field(default_factory=set)
    trusted_id: str | None = None

    def report(self) -> dict:
        return {**asdict(self.network), "identity": self.network.identity, "status": self.status,
                "reason": self.reason, "trusted_id": self.trusted_id,
                "rules": [asdict(r) for r in sorted(self.rules)]}


def canonical(components: dict[str, str]) -> str:
    return "|".join(f"{k}={components[k]}" for k in ("medium", "ssid", "gw_mac", "nm") if k in components)


def run(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- detección

def parse_ipv4_addresses(output: str) -> dict[str, list[str]]:
    """``ip -4 -o addr show scope global`` → {interfaz: ["192.168.10.23/24", ...]}."""
    found: dict[str, list[str]] = {}
    for line in output.splitlines():
        match = re.match(r"^\d+:\s+(\S+)\s+inet\s+(\d{1,3}(?:\.\d{1,3}){3}/\d{1,2})\b", line)
        if match:
            found.setdefault(match.group(1).split("@")[0], []).append(match.group(2))
    return found


def parse_default_routes(output: str) -> dict[str, str]:
    """``ip -4 route show default`` → {interfaz: gateway} (menor métrica por interfaz)."""
    best: dict[str, tuple[int, str]] = {}
    for line in output.splitlines():
        if not line.startswith("default"):
            continue
        dev = re.search(r"\bdev\s+(\S+)", line)
        via = re.search(r"\bvia\s+(\S+)", line)
        metric = re.search(r"\bmetric\s+(\d+)", line)
        if not dev or not via:
            continue
        value = int(metric.group(1)) if metric else 0
        if dev.group(1) not in best or value < best[dev.group(1)][0]:
            best[dev.group(1)] = (value, via.group(1))
    return {iface: gateway for iface, (_, gateway) in best.items()}


def parse_ssid(iw_output: str) -> str | None:
    match = re.search(r"^[ \t]*SSID:[ \t]*(\S.*?)[ \t]*$", iw_output, re.M)
    return match.group(1) if match else None


def parse_neigh_mac(neigh_output: str) -> str | None:
    match = re.search(r"\blladdr\s+([0-9a-fA-F:]{17})\b", neigh_output)
    mac = match.group(1).lower() if match else None
    return mac if mac and _MAC.match(mac) and mac != "00:00:00:00:00:00" else None


def parse_nmcli_active(output: str) -> dict[str, str]:
    """``nmcli -t -f DEVICE,UUID connection show --active`` → {interfaz: UUID}."""
    found = {}
    for line in output.splitlines():
        fields = re.split(r"(?<!\\):", line)
        if len(fields) >= 2 and fields[0] and fields[1]:
            found.setdefault(fields[0], fields[1])
    return found


def interface_kind(iface: str) -> str | None:
    """``wired``/``wifi`` para NIC físicas aptas; ``None`` para todo lo demás."""
    base = SYSFS / iface
    if not (base / "device").exists() or (base / "master").exists():
        return None  # virtual (docker0, br-*, veth, tun, wg...) o esclava de un bridge
    if (base / "wireless").exists() or (base / "phy80211").exists():
        return "wifi"
    try:
        return "wired" if (base / "type").read_text().strip() == "1" else None  # ARPHRD_ETHER
    except OSError:
        return None


def interface_up(iface: str) -> bool:
    try:
        return (SYSFS / iface / "operstate").read_text().strip() in ("up", "unknown")
    except OSError:
        return False


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


def _ssid(iface: str) -> str | None:
    try:
        return parse_ssid(run("iw", "dev", iface, "link"))
    except (OSError, subprocess.CalledProcessError):
        return None


def _nm_profiles() -> tuple[dict[str, str], str]:
    """({interfaz: UUID}, estado global: ok | absent | error)."""
    try:
        result = subprocess.run(["nmcli", "-t", "-f", "DEVICE,UUID", "connection", "show", "--active"],
                                capture_output=True, text=True, timeout=10, check=False)
    except FileNotFoundError:
        return {}, "absent"
    except (OSError, subprocess.TimeoutExpired):
        return {}, "error"
    if result.returncode == 8:  # "NetworkManager is not running"
        return {}, "absent"
    if result.returncode != 0:
        return {}, "error"
    return parse_nmcli_active(result.stdout), "ok"


def detect_networks() -> list[Network]:
    """Todas las LAN IPv4 activas en interfaces Ethernet/Wi-Fi físicas, cada una por separado."""
    addresses = parse_ipv4_addresses(run("ip", "-4", "-o", "addr", "show", "scope", "global"))
    gateways = parse_default_routes(run("ip", "-4", "route", "show", "default"))
    candidates = [(iface, interface_kind(iface)) for iface in sorted(addresses)]
    candidates = [(iface, kind) for iface, kind in candidates if kind and interface_up(iface)]
    profiles, nm_global = _nm_profiles() if candidates else ({}, "absent")
    networks = []
    for iface, kind in candidates:
        address = addresses[iface][0]
        gateway = gateways.get(iface)
        nm_uuid = profiles.get(iface)
        nm_state = nm_global if nm_global != "ok" else ("ok" if nm_uuid else "unmanaged")
        networks.append(Network(
            iface=iface, address=address, subnet=str(ipaddress.ip_interface(address).network),
            gateway=gateway, medium=kind, ssid=_ssid(iface) if kind == "wifi" else None,
            gw_mac=_gateway_mac(iface, gateway), nm_uuid=nm_uuid, nm_state=nm_state))
    return networks


def subnet_is_acceptable(subnet: str | None) -> bool:
    if not subnet:
        return False
    try:
        net = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return False
    return net.version == 4 and any(net.subnet_of(block) for block in RFC1918)


# ---------------------------------------------------------------- configuración y estado

def load_conf() -> dict:
    if CONF.exists():
        return json.loads(CONF.read_text(encoding="utf-8"))
    # Sin "publish_api": el reconciliador no toca el env hasta que configurar-acceso-lan.sh lo pida.
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
    """Estado por interfaz. El formato anterior (una sola red) se convierte."""
    if not STATE.exists():
        return {"interfaces": {}}
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if "interfaces" in state:
        return state
    previous = state.get("network") or {}
    converted: dict = {"interfaces": {}}
    if previous.get("iface"):
        converted["interfaces"][previous["iface"]] = {
            "subnet": previous.get("subnet"), "gateway": previous.get("gateway"), "status": TRUSTED,
            "hold_since": state.get("hold_since"),
            "rules": [r for r in state.get("rules", []) if r.get("iface") == previous["iface"]]}
    return converted


def ports(conf: dict) -> list[tuple[str, str]]:
    found = list(BASE_PORTS)
    for option, extra in OPTIONAL_PORTS.items():
        if conf.get(option):
            found.extend(extra)
    return found


# ---------------------------------------------------------------- decisión por LAN

def evaluate(conf: dict, network: Network, previous: dict | None = None) -> Decision:
    """Qué corresponde a UNA interfaz, sin mirar las demás."""
    if not subnet_is_acceptable(network.subnet):
        return Decision(network, NOT_PRIVATE, f"subred {network.subnet} no es LAN privada RFC1918: no se abre nada")
    if network.components() is None:
        previous = previous or {}
        applied = {Rule(**r) for r in previous.get("rules", [])}
        same_place = (previous.get("subnet"), previous.get("gateway")) == (network.subnet, network.gateway)
        since = previous.get("hold_since")
        elapsed = (_now() - datetime.fromisoformat(since)).total_seconds() if since else 0.0
        if applied and same_place and previous.get("status") in (TRUSTED, HOLD) and elapsed < HOLD_SECONDS:
            return Decision(network, HOLD, (
                f"identidad de {network.iface} temporalmente no disponible; se mantienen sus reglas "
                f"({network.subnet}, HOLD {int(elapsed)}s/{HOLD_SECONDS}s)"), applied)
        return Decision(network, UNIDENTIFIED,
                        f"no se pudo identificar la red de {network.iface} (gateway/SSID/NetworkManager)")
    entry = matching_entry(conf, network)
    if entry is None:
        return Decision(network, UNTRUSTED, (
            f"red {network.identity} en {network.iface} no confiable: "
            f"trust-current --interface {network.iface} si corresponde"))
    return Decision(network, TRUSTED, f"red confiable {entry['id']} en {network.iface} ({network.subnet})",
                    {Rule(network.iface, network.subnet, p, proto) for p, proto in ports(conf)}, entry["id"])


def evaluate_all(conf: dict, networks: list[Network], state: dict) -> list[Decision]:
    previous = state.get("interfaces", {})
    return [evaluate(conf, n, previous.get(n.iface)) for n in networks]


def desired_rules(decisions: list[Decision]) -> set[Rule]:
    return set().union(*(d.rules for d in decisions)) if decisions else set()


# ---------------------------------------------------------------- UFW

def ufw_active() -> bool:
    try:
        return "Status: active" in run("ufw", "status")
    except (OSError, subprocess.CalledProcessError):
        return False


def ufw_default_incoming() -> str | None:
    try:
        match = re.search(r"^Default:\s*(\w+)\s*\(incoming\)", run("ufw", "status", "verbose"), re.M)
    except (OSError, subprocess.CalledProcessError):
        return None
    return match.group(1) if match else None


def parse_ufw_numbered(output: str) -> tuple[list[tuple[int, Rule | None]], list[int]]:
    """(reglas propias [(número, Rule o None si no se reconoce)], números de reglas legado)."""
    managed: list[tuple[int, Rule | None]] = []
    legacy: list[int] = []
    for line in output.splitlines():
        match = _UFW_COMMENT.match(line)
        if not match:
            continue
        number, comment = int(match.group(1)), match.group(2)
        if comment == COMMENT:
            full = _UFW_RULE.match(line)
            managed.append((number, Rule(full.group(4), full.group(5), full.group(2), full.group(3))
                            if full else None))
        elif comment in LEGACY_COMMENTS:
            legacy.append(number)
    return managed, legacy


def rules_in_place(desired: set[Rule]) -> bool:
    """Sólo lectura: ¿UFW tiene exactamente las reglas propias deseadas (y ninguna legado)?"""
    try:
        managed, legacy = parse_ufw_numbered(run("ufw", "status", "numbered"))
    except (OSError, subprocess.CalledProcessError):
        return False
    present = [rule for _, rule in managed]
    return None not in present and sorted(present) == sorted(desired) and not legacy


def reconcile(desired: set[Rule]) -> dict:
    """Borra sólo las reglas propias que sobran (y legado) y añade las que faltan.

    No depende del archivo de estado: las reglas propias se reconocen por su
    comentario, así que un estado perdido nunca deja huérfanas. Los números se
    toman de un único listado y se borran de mayor a menor (sin renumerar).
    """
    managed, legacy = parse_ufw_numbered(run("ufw", "status", "numbered"))
    kept: set[Rule] = set()
    delete = list(legacy)
    removed = []
    for number, rule in managed:
        if rule is None or rule not in desired or rule in kept:
            delete.append(number)
            if rule is not None and rule not in desired:
                removed.append(rule)
        else:
            kept.add(rule)
    added = sorted(desired - kept)
    for number in sorted(delete, reverse=True):
        run("ufw", "--force", "delete", str(number))
    for rule in added:
        run("ufw", "allow", *rule.ufw_args(), "comment", COMMENT)
    verified = rules_in_place(desired)
    return {"added": [asdict(r) for r in added], "removed": [asdict(r) for r in sorted(removed)],
            "legacy_removed": len(legacy), "changed": bool(delete or added), "verified": verified}


def apply(conf: dict, networks: list[Network], *, dry_run: bool = False) -> dict:
    state = load_state()
    decisions = evaluate_all(conf, networks, state)
    desired = desired_rules(decisions)
    detected = {n.iface for n in networks}
    report = {
        "networks": [d.report() for d in decisions],
        "ausentes": sorted(set(state.get("interfaces", {})) - detected),
        "rules": [asdict(r) for r in sorted(desired)],
        "published": sorted(d.network.iface for d in decisions if d.status == TRUSTED),
        "hold": sorted(d.network.iface for d in decisions if d.status == HOLD),
        "added": [], "removed": [], "legacy_removed": 0, "changed": False, "verified": False,
    }
    if dry_run:
        report["verified"] = rules_in_place(desired)
        return report
    report.update(reconcile(desired))
    interfaces = {}
    for decision in decisions:
        previous = state.get("interfaces", {}).get(decision.network.iface, {})
        entry = {"identity": decision.network.identity, "subnet": decision.network.subnet,
                 "gateway": decision.network.gateway, "status": decision.status,
                 "rules": [asdict(r) for r in sorted(decision.rules)]}
        if decision.status == HOLD:
            # En HOLD se conserva la última identidad conocida para seguir comparando.
            entry["identity"] = previous.get("identity")
            entry["hold_since"] = previous.get("hold_since") or _now().isoformat()
        interfaces[decision.network.iface] = entry
    save_json(STATE, {"interfaces": interfaces, "updated_at": _now().isoformat()})
    return report


# ---------------------------------------------------------------- confianza

def trust(conf: dict, networks: list[Network], interfaces: list[str] | None = None) -> dict:
    """Confía explícitamente en la LAN de cada interfaz indicada (todo o nada)."""
    by_iface = {n.iface: n for n in networks}
    if interfaces:
        missing = [i for i in interfaces if i not in by_iface]
        if missing:
            raise SystemExit(f"Sin LAN IPv4 activa (Ethernet/Wi-Fi) en: {', '.join(missing)}. "
                             f"Activas: {', '.join(by_iface) or 'ninguna'}.")
        chosen = [by_iface[i] for i in interfaces]
    elif len(networks) == 1:
        chosen = networks
    elif not networks:
        raise SystemExit("No hay ninguna LAN IPv4 activa en interfaces Ethernet/Wi-Fi.")
    else:
        listing = "; ".join(f"{n.iface} ({n.medium}, {n.subnet}, gw {n.gateway}, "
                            f"{'SSID ' + n.ssid if n.ssid else 'cable'})" for n in networks)
        raise SystemExit(f"Hay varias LAN activas: {listing}. Indique cuál(es) confiar con "
                         "--interface <if> (repetible); nunca se confía una LAN por estar enchufada.")
    for network in chosen:
        if network.components() is None:
            raise SystemExit(f"No se pudo identificar la red de {network.iface} (MAC del gateway, SSID o "
                             "perfil de NetworkManager); no se confía a ciegas.")
        if not subnet_is_acceptable(network.subnet):
            raise SystemExit(f"La subred {network.subnet} de {network.iface} no es LAN privada RFC1918; "
                             "no se confía.")
    for network in chosen:
        if matching_entry(conf, network) is None:
            components = network.components()
            conf.setdefault("trusted_networks", []).append({
                "id": canonical(components), "components": components, "added_at": _now().isoformat(),
                "first_subnet": network.subnet, "first_iface": network.iface})
    save_json(CONF, conf)
    return conf


# ---------------------------------------------------------------- API

def read_api_host() -> str | None:
    try:
        text = ENV_FILE.read_text(encoding="utf-8")
    except OSError:
        return None
    values = [l.split("=", 1)[1].strip() for l in text.splitlines() if l.startswith("SERVER_OFICINA_HOST=")]
    return values[-1] if values else None


def api_target(conf: dict, report: dict, active: bool, default_incoming: str | None) -> str:
    safe = active and default_incoming in ("deny", "reject") and report["verified"] and report["published"]
    return "0.0.0.0" if conf.get("publish_api") and safe else "127.0.0.1"


def write_api_host(host: str) -> bool:
    """Reescribe SERVER_OFICINA_HOST (atómico, conserva dueño y modo) y reinicia la API si corre."""
    current = read_api_host()
    if current is None or current == host:
        return False
    info = ENV_FILE.stat()
    lines = [f"SERVER_OFICINA_HOST={host}" if l.startswith("SERVER_OFICINA_HOST=") else l
             for l in ENV_FILE.read_text(encoding="utf-8").splitlines()]
    temp = ENV_FILE.with_name(f".{ENV_FILE.name}.tmp")
    temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(temp, info.st_mode & 0o7777)
    if os.geteuid() == 0:
        os.chown(temp, info.st_uid, info.st_gid)
    os.replace(temp, ENV_FILE)
    subprocess.run(["systemctl", "try-restart", "server-oficina.service"], check=False, capture_output=True)
    return True


# ---------------------------------------------------------------- auditoría (sólo lectura)

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def parse_avahi_conf(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line and not line.startswith("["):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _split_list(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def audit_avahi(published: list[str], text: str, active: str, hostname: str) -> dict:
    conf = parse_avahi_conf(text)
    allow, deny = _split_list(conf.get("allow-interfaces")), _split_list(conf.get("deny-interfaces"))
    name = conf.get("host-name") or hostname
    problems = []
    if active != "active":
        problems.append(f"avahi-daemon no está activo ({active}): server-oficina.local no se anuncia")
    if conf.get("enable-reflector", "no").lower() == "yes":
        problems.append("enable-reflector=yes: Avahi reenviaría mDNS entre LAN; debe estar en no")
    if conf.get("use-ipv4", "yes").lower() == "no":
        problems.append("use-ipv4=no: no se anunciaría la dirección IPv4 en ninguna LAN")
    if conf.get("publish-addresses", "yes").lower() == "no":
        problems.append("publish-addresses=no: server-oficina.local no resolvería")
    for iface in published:
        if iface in deny or (allow and iface not in allow):
            problems.append(f"Avahi excluye {iface} (allow/deny-interfaces): no se anuncia en esa LAN")
    if name != HOSTNAME:
        problems.append(f"el nombre mDNS sería {name}.local, no {HOSTNAME}.local")
    return {"activo": active, "nombre": f"{name}.local", "allow_interfaces": allow, "deny_interfaces": deny,
            "reflector": conf.get("enable-reflector", "no"), "problemas": problems}


def audit_forwarding(ip_forward: str, forward_policy: str | None, ufw_forward: str | None,
                     networks: list[Network], nat_rules: str) -> dict:
    """La Latitude no debe enrutar entre sus LAN (ni bridge ni NAT entre ellas)."""
    problems = []
    if ip_forward.strip() == "1" and forward_policy != "DROP":
        problems.append(f"net.ipv4.ip_forward=1 con política FORWARD {forward_policy}: podría enrutar entre LAN")
    if ufw_forward not in (None, "DROP", "REJECT"):
        problems.append(f"UFW DEFAULT_FORWARD_POLICY={ufw_forward}: debe ser DROP")
    for network in networks:
        if network.subnet and re.search(rf"-s {re.escape(network.subnet)}\b.*MASQUERADE", nat_rules):
            problems.append(f"NAT (MASQUERADE) de la LAN {network.subnet}: la Latitude no debe hacer NAT")
    return {"ip_forward": ip_forward.strip(), "forward_policy": forward_policy, "ufw_forward_policy": ufw_forward,
            "nota": ("ip_forward=1 es normal con Docker; lo que impide enrutar entre LAN es la política "
                     "FORWARD DROP" if ip_forward.strip() == "1" else "sin forwarding"),
            "problemas": problems}


def parse_listeners(ss_output: str) -> dict[str, list[str]]:
    """``ss -H -lntu`` → {"tcp/8080": ["0.0.0.0", ...], ...}."""
    found: dict[str, list[str]] = {}
    for line in ss_output.splitlines():
        cols = line.split()
        if len(cols) < 5 or cols[0] not in ("tcp", "udp"):
            continue
        host, _, port = cols[4].rpartition(":")
        found.setdefault(f"{cols[0]}/{port}", []).append(host.strip("[]") or "*")
    return found


def audit_listeners(listeners: dict[str, list[str]], published: list[str], api_host: str | None) -> dict:
    wildcard = {"0.0.0.0", "*", "::"}
    problems = []
    syncthing = {k: listeners.get(k, []) for k in ("tcp/22000", "udp/22000", "udp/21027")}
    for key, hosts in syncthing.items():
        if hosts and not wildcard & set(hosts):
            problems.append(f"Syncthing {key} sólo en {hosts}: no escucharía en todas las LAN")
    api = listeners.get("tcp/8080", [])
    if published and api and not wildcard & set(api):
        problems.append(f"la API escucha sólo en {api} aunque hay LAN confiables publicadas")
    if not published and wildcard & set(api):
        problems.append("la API escucha en 0.0.0.0 sin ninguna LAN confiable publicada")
    return {"syncthing": syncthing, "api": api, "api_host_env": api_host, "problemas": problems}


def audit(conf: dict, networks: list[Network]) -> dict:
    report = apply(conf, networks, dry_run=True)
    published = report["published"]

    def sh(*args: str) -> str:
        try:
            return subprocess.run(args, capture_output=True, text=True, timeout=10, check=False).stdout
        except (OSError, subprocess.TimeoutExpired):
            return ""

    forward_policy = re.search(r"^-P FORWARD (\w+)", sh("iptables", "-S", "FORWARD"), re.M)
    ufw_forward = re.search(r'^DEFAULT_FORWARD_POLICY="?(\w+)"?', _read(UFW_DEFAULTS), re.M)
    mdns_generic = bool(re.search(r"^-A ufw-before-input .*-d 224\.0\.0\.251 .*--dport 5353 .*ACCEPT",
                                  _read(UFW_BEFORE_RULES), re.M))
    sections = {
        "avahi": audit_avahi(published, _read(AVAHI_CONF),
                             sh("systemctl", "is-active", "avahi-daemon").strip() or "desconocido",
                             socket.gethostname()),
        "enrutamiento": audit_forwarding(_read(Path("/proc/sys/net/ipv4/ip_forward")) or "0",
                                         forward_policy.group(1) if forward_policy else None,
                                         ufw_forward.group(1) if ufw_forward else None,
                                         networks, sh("iptables", "-t", "nat", "-S", "POSTROUTING")),
        "escucha": audit_listeners(parse_listeners(sh("ss", "-H", "-lntu")), published, read_api_host()),
    }
    sections["ufw"] = {
        "activo": ufw_active(), "entrada_por_defecto": ufw_default_incoming(),
        "mdns_multicast_generico_en_before_rules": mdns_generic,
        "nota": ("before.rules acepta mDNS multicast (224.0.0.251:5353) en cualquier interfaz: es link-local "
                 "(nunca se enruta) y lo trae UFW por defecto; las reglas 5353 propias limitan el mDNS unicast"
                 if mdns_generic else "sin aceptación genérica de mDNS en before.rules"),
        "problemas": [] if ufw_active() else ["UFW inactivo"],
    }
    problems = [p for s in sections.values() for p in s["problemas"]]
    return {"networks": report["networks"], "published": published, **sections, "problemas": problems}


# ---------------------------------------------------------------- CLI

def acquire_lock(timeout: float = 180.0):
    """Un solo actor a la vez (timer, dispatcher, configurar-acceso-lan.sh, operador).

    ``configurar-acceso-lan.sh`` toma el mismo bloqueo durante toda la
    publicación y exporta ``SO_LAN_FIREWALL_LOCK_HELD=1`` para sus llamadas.
    """
    if os.environ.get("SO_LAN_FIREWALL_LOCK_HELD") == "1":
        return None
    import fcntl
    try:
        handle = open(LOCK, "a")  # noqa: SIM115 - se mantiene abierto hasta salir
    except OSError:
        return None
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            if time.monotonic() > deadline:
                raise SystemExit(f"otro proceso retiene {LOCK}; no se modificó nada")
            time.sleep(0.5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    ap = sub.add_parser("apply")
    ap.add_argument("--require-rules", action="store_true",
                    help="código 3 si no queda ninguna LAN confiable con reglas verificadas")
    ap.add_argument("--sync-api", action="store_true", help="ajustar SERVER_OFICINA_HOST (servicio systemd)")
    tp = sub.add_parser("trust-current")
    tp.add_argument("--interface", action="append", dest="interfaces", metavar="IF",
                    help="interfaz cuya LAN actual se confía (repetible)")
    tp.add_argument("--sync-api", action="store_true")
    for name in ("enable", "disable"):
        opt = sub.add_parser(name)
        opt.add_argument("option", choices=sorted(OPTIONAL_PORTS))
    api = sub.add_parser("api")
    api.add_argument("mode", choices=["on", "off"])
    sub.add_parser("audit")
    args = parser.parse_args(argv)

    lock = None if args.cmd in {"status", "audit"} else acquire_lock()
    conf = load_conf()
    networks = detect_networks()
    if args.cmd == "audit":
        result = audit(conf, networks)
        print("LAN_AUDIT " + json.dumps(result, ensure_ascii=False))
        return 5 if result["problemas"] else 0
    if args.cmd in {"enable", "disable"}:
        conf[args.option] = args.cmd == "enable"
        save_json(CONF, conf)
    if args.cmd == "api":
        conf["publish_api"] = args.mode == "on"
        save_json(CONF, conf)
    if args.cmd == "trust-current":
        conf = trust(conf, networks, args.interfaces)
    active = ufw_active()
    report = apply(conf, networks, dry_run=args.cmd == "status" or not active)
    report["ufw"] = "activo" if active else "inactivo: no se modificó nada"
    legacy_entries = len(conf.get("trusted_networks", [])) - len(trusted_entries(conf))
    if legacy_entries:
        report["entradas_legado_ignoradas"] = legacy_entries
    target = api_target(conf, report, active, ufw_default_incoming() if active else None)
    report["api"] = {"publicar": bool(conf.get("publish_api")), "actual": read_api_host(), "objetivo": target,
                     "cambiado": False}
    if getattr(args, "sync_api", False) and conf.get("publish_api") is not None:
        report["api"]["cambiado"] = write_api_host(target)
    print("LAN_FIREWALL " + json.dumps(report, ensure_ascii=False))
    if lock is not None:
        lock.close()
    if args.cmd == "apply" and args.require_rules:
        return 0 if active and report["published"] and report["verified"] else 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
