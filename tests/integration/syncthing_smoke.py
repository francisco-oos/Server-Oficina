#!/usr/bin/env python3
from __future__ import annotations

"""Prueba E2E contra tres procesos Syncthing reales.

Valida transporte; no simula la lógica interna de Syncthing. Se ejecuta en CI
sobre contenedores efímeros y usa topología estrella: pc1 ↔ hub ↔ pc2.
"""

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

API_KEY = "server-oficina-integration"
ROOT = Path(os.environ["IT_ROOT"]).resolve()
COMPOSE = Path(__file__).with_name("syncthing-compose.yml").resolve()
NODES = {
    "hub": ("http://127.0.0.1:18384", ROOT / "hub"),
    "pc1": ("http://127.0.0.1:18385", ROOT / "pc1"),
    "pc2": ("http://127.0.0.1:18386", ROOT / "pc2"),
}


def request(node: str, method: str, path: str, *, params=None, payload=None):
    base = NODES[node][0]
    query = "?" + urlencode(params) if params else ""
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        base + path + query,
        data=data,
        method=method,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
    )
    with urlopen(req, timeout=10) as response:
        body = response.read()
        return json.loads(body.decode("utf-8")) if body else None


def wait_until(label: str, predicate, timeout: float = 90.0, interval: float = 0.5):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except Exception as exc:
            last = repr(exc)
        time.sleep(interval)
    raise AssertionError(f"Timeout esperando {label}; último={last!r}")


def wait_api(node: str):
    return wait_until(f"API {node}", lambda: request(node, "GET", "/rest/system/status"), timeout=60)


def scan(node: str):
    request(node, "POST", "/rest/db/scan", params={"folder": "lab"})


def file_bytes(node: str, relative: str) -> bytes | None:
    path = NODES[node][1] / relative
    return path.read_bytes() if path.is_file() else None


def wait_content(relative: str, expected: bytes, nodes=("hub", "pc1", "pc2")):
    for node in nodes:
        wait_until(
            f"{relative}={hashlib.sha256(expected).hexdigest()[:10]} en {node}",
            lambda node=node: file_bytes(node, relative) == expected,
        )


def wait_absent(relative: str, nodes=("hub", "pc1", "pc2")):
    for node in nodes:
        wait_until(f"{relative} ausente en {node}", lambda node=node: not (NODES[node][1] / relative).exists())


def configure():
    for node in NODES:
        wait_api(node)
    ids = {node: request(node, "GET", "/rest/system/status")["myID"] for node in NODES}

    # CI usa direcciones internas estáticas para que la prueba sea determinista.
    # Producción usa "dynamic" + descubrimiento local.
    addresses = {"hub": "tcp://hub:22000", "pc1": "tcp://pc1:22000", "pc2": "tcp://pc2:22000"}
    peers = {"hub": ("pc1", "pc2"), "pc1": ("hub",), "pc2": ("hub",)}

    for node in NODES:
        request(node, "PATCH", "/rest/config/options", payload={
            "globalAnnounceEnabled": False,
            "relaysEnabled": False,
            "natEnabled": False,
            "localAnnounceEnabled": False,
            "crashReportingEnabled": False,
        })
        for peer in peers[node]:
            request(node, "POST", "/rest/config/devices", payload={
                "deviceID": ids[peer],
                "name": peer,
                "addresses": [addresses[peer]],
                "introducer": False,
                "autoAcceptFolders": False,
                "paused": False,
            })

    for node in NODES:
        devices = [{"deviceID": ids[p]} for p in peers[node]]
        request(node, "POST", "/rest/config/folders", payload={
            "id": "lab",
            "label": "Server Oficina Integration LAB",
            "filesystemType": "basic",
            "path": "/sync",
            "type": "sendreceive",
            "devices": devices,
            "rescanIntervalS": 3600,
            "fsWatcherEnabled": True,
            "fsWatcherDelayS": 1,
            "autoNormalize": True,
            "ignorePerms": True,
            "maxConflicts": -1,
            "paused": False,
            "versioning": {"type": "staggered", "params": {"maxAge": "31536000"}},
        })

    def hub_connected():
        data = request("hub", "GET", "/rest/system/connections").get("connections", {})
        return all(data.get(ids[p], {}).get("connected") for p in ("pc1", "pc2"))

    wait_until("pc1 y pc2 conectadas al hub", hub_connected, timeout=90)
    return ids


def compose(*args: str):
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), *args],
        check=True,
        env={**os.environ, "IT_ROOT": str(ROOT)},
    )


def test_basic_create_modify():
    payload = b"Server Oficina: primera version\n"
    path = NODES["pc1"][1] / "creacion.txt"
    path.write_bytes(payload)
    scan("pc1")
    wait_content("creacion.txt", payload)

    updated = b"Server Oficina: segunda version desde pc2\n"
    (NODES["pc2"][1] / "creacion.txt").write_bytes(updated)
    scan("pc2")
    wait_content("creacion.txt", updated)


def test_rename():
    old = NODES["pc1"][1] / "rename-old.txt"
    old.write_bytes(b"rename-safe")
    scan("pc1")
    wait_content("rename-old.txt", b"rename-safe")

    old.rename(NODES["pc1"][1] / "rename-new.txt")
    scan("pc1")
    wait_content("rename-new.txt", b"rename-safe")
    wait_absent("rename-old.txt")


def test_delete_and_remote_versioning():
    path = NODES["pc1"][1] / "delete-me.txt"
    path.write_bytes(b"contenido que debe poder recuperarse")
    scan("pc1")
    wait_content("delete-me.txt", b"contenido que debe poder recuperarse")

    path.unlink()
    scan("pc1")
    wait_absent("delete-me.txt")

    hub_versions = NODES["hub"][1] / ".stversions"
    wait_until(
        "versión remota archivada en hub/.stversions",
        lambda: hub_versions.exists() and any(p.is_file() and "delete-me" in p.name for p in hub_versions.rglob("*")),
        timeout=90,
    )


def test_offline_conflict_preserves_both():
    base = b"BASE\n"
    target1 = NODES["pc1"][1] / "concurrent.txt"
    target1.write_bytes(base)
    scan("pc1")
    wait_content("concurrent.txt", base)

    compose("stop", "hub")
    try:
        left = b"CAMBIO-PC1\n"
        right = b"CAMBIO-PC2\n"
        target1.write_bytes(left)
        (NODES["pc2"][1] / "concurrent.txt").write_bytes(right)
        scan("pc1")
        scan("pc2")
        time.sleep(2)
    finally:
        compose("start", "hub")
        wait_api("hub")

    def conflict_exists():
        return any(
            ".sync-conflict-" in p.name
            for node in NODES
            for p in NODES[node][1].glob("concurrent.sync-conflict-*")
        )

    wait_until("copia de conflicto concurrente", conflict_exists, timeout=120)
    # Ningún contenido concurrente puede desaparecer del conjunto convergente.
    def both_contents_present():
        contents = set()
        for node in NODES:
            for p in NODES[node][1].glob("concurrent*"):
                if p.is_file():
                    contents.add(p.read_bytes())
        return left in contents and right in contents

    wait_until("ambas versiones concurrentes preservadas", both_contents_present, timeout=120)


def test_restart_and_batch():
    batch = NODES["pc2"][1] / "lote"
    batch.mkdir(exist_ok=True)
    for i in range(100):
        (batch / f"archivo-{i:03d}.txt").write_text(f"{i}\n", encoding="utf-8")
    scan("pc2")

    wait_until(
        "100 archivos del lote en hub",
        lambda: len(list((NODES["hub"][1] / "lote").glob("archivo-*.txt"))) == 100,
        timeout=120,
    )
    compose("restart", "pc2")
    wait_api("pc2")

    marker = b"despues-del-reinicio"
    (NODES["pc1"][1] / "post-restart.txt").write_bytes(marker)
    scan("pc1")
    wait_content("post-restart.txt", marker)


def test_large_file_hash():
    block = bytes(range(256))
    payload = block * (4 * 1024 * 1024 // len(block))
    expected = hashlib.sha256(payload).hexdigest()
    (NODES["pc1"][1] / "4MiB.bin").write_bytes(payload)
    scan("pc1")
    wait_content("4MiB.bin", payload)
    for node in NODES:
        actual = hashlib.sha256((NODES[node][1] / "4MiB.bin").read_bytes()).hexdigest()
        assert actual == expected


def main() -> int:
    for _, folder in NODES.values():
        folder.mkdir(parents=True, exist_ok=True)

    ids = configure()
    print("SYNC_IT_DEVICE_IDS", {k: v[:7] for k, v in ids.items()}, flush=True)
    test_basic_create_modify()
    test_rename()
    test_delete_and_remote_versioning()
    test_offline_conflict_preserves_both()
    test_restart_and_batch()
    test_large_file_hash()
    print("SYNCTHING_INTEGRATION_OK", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        compose("logs", "--no-color")
        raise
