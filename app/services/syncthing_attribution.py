from __future__ import annotations

"""Atribución técnica de dispositivo a partir de Syncthing (sin Companion).

Syncthing registra para cada versión de archivo el ``modifiedBy``: el ID corto
(7 caracteres) del dispositivo que introdujo ese cambio. Con él Server Oficina
puede saber **qué equipo** originó una versión observada en el hub.

Lo que NO aporta: la persona ni la sesión humana. Esa atribución requiere el
Companion de Windows (login de estación + journal local). Por eso cada
atribución declara ``scope="DEVICE"`` y ``person=None``.

La atribución nunca bloquea la ingesta: si la API de Syncthing no responde,
la versión se registra igual con ``method="none"`` y la causa.
"""

import re
from datetime import datetime
from typing import Any, Callable, Protocol

from app.services.file_watcher import FileObservation

_FRACTION = re.compile(r"\.\d+")


class FileInfoClient(Protocol):
    def file_info(self, *, folder: str, relative_path: str) -> dict: ...


def short_device_id(device_id: str) -> str:
    """ID corto de Syncthing: primeros 7 caracteres del Device ID sin guiones."""
    return device_id.replace("-", "").strip().upper()[:7]


def _modified_seconds(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(_FRACTION.sub("", value.replace("Z", "+00:00"))).timestamp())
    except ValueError:
        return None


class SyncthingAttributor:
    """Callable para ``ingest_stable_snapshot(attribute=...)``."""

    def __init__(
        self,
        client: FileInfoClient,
        *,
        folder_id: str,
        peers_by_short_id: dict[str, tuple[str, str]],
        log: Callable[[str], None] | None = None,
    ):
        self.client = client
        self.folder_id = folder_id
        self.peers = peers_by_short_id
        self.log = log
        self.disabled_reason: str | None = None

    def __call__(self, observation: FileObservation) -> dict[str, Any]:
        if self.disabled_reason:
            return {"method": "none", "scope": "DEVICE", "person": None, "reason": self.disabled_reason}
        try:
            info = self.client.file_info(folder=self.folder_id, relative_path=observation.disk_path) or {}
        except Exception as exc:  # noqa: BLE001 - la atribución nunca bloquea la ingesta
            # Un fallo de la API no se reintenta archivo por archivo en esta pasada.
            self.disabled_reason = f"API Syncthing no disponible: {exc.__class__.__name__}"
            if self.log:
                self.log(f"LOCAL_CLOUD_ATTRIBUTION_UNAVAILABLE folder={self.folder_id} reason={self.disabled_reason}")
            return {"method": "none", "scope": "DEVICE", "person": None, "reason": self.disabled_reason}
        entry = info.get("local") or info.get("global") or {}
        short = (entry.get("modifiedBy") or "").upper() or None
        size_ok = entry.get("size") == observation.size_bytes
        mtime_ok = _modified_seconds(entry.get("modified")) == observation.mtime_ns // 1_000_000_000
        peer = self.peers.get(short or "")
        return {
            "source_peer_id": peer[0] if peer else None,
            "method": "syncthing_modified_by",
            "scope": "DEVICE",
            "person": None,
            "device_short_id": short,
            "peer_code": peer[1] if peer else None,
            # Verificada sólo si Syncthing describe exactamente el archivo observado.
            "verified": bool(short) and size_ok and mtime_ok,
        }
