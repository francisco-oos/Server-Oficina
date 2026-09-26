from __future__ import annotations

"""Contratos de topología para la Nube Local de Server Oficina.

Este módulo NO toca Syncthing. Sólo construye configuraciones deterministas que
pueden revisarse y probarse antes de aplicarlas. La primera topología soportada
es estrella: las PCs comparten con la Latitude y la Latitude actúa como hub.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SyncFolderPlan:
    folder_id: str
    label: str
    path: str
    device_ids: tuple[str, ...]


def lan_only_options_patch() -> dict:
    """Opciones mínimas para impedir que el hub dependa de Internet."""
    return {
        "globalAnnounceEnabled": False,
        "relaysEnabled": False,
        "natEnabled": False,
        "localAnnounceEnabled": True,
    }


def build_device_config(device_id: str, *, name: str) -> dict:
    device_id = (device_id or "").strip()
    if not device_id:
        raise ValueError("device_id requerido")
    return {
        "deviceID": device_id,
        "name": name.strip() or device_id,
        "addresses": ["dynamic"],
        "autoAcceptFolders": False,
        "introducer": False,
        "paused": False,
    }


def build_folder_config(plan: SyncFolderPlan, *, versioning: bool = True) -> dict:
    root = Path(plan.path)
    if not plan.folder_id.strip():
        raise ValueError("folder_id requerido")
    if not str(root):
        raise ValueError("path requerido")
    devices = [{"deviceID": device_id} for device_id in sorted(set(plan.device_ids)) if device_id]
    payload = {
        "id": plan.folder_id.strip(),
        "label": plan.label.strip() or plan.folder_id.strip(),
        "filesystemType": "basic",
        "path": str(root),
        "type": "sendreceive",
        "devices": devices,
        "rescanIntervalS": 300,
        "fsWatcherEnabled": True,
        "fsWatcherDelayS": 5,
        "autoNormalize": True,
        "ignorePerms": False,
        "maxConflicts": 25,
        "paused": False,
    }
    if versioning:
        payload["versioning"] = {
            "type": "staggered",
            "params": {"maxAge": str(365 * 24 * 60 * 60)},
        }
    return payload


def topology_summary(*, peer_count: int, share_count: int) -> dict:
    return {
        "mode": "STAR",
        "hub": "server-oficina",
        "peer_count": peer_count,
        "share_count": share_count,
        "internet_required": False,
        "conflict_policy": "preserve_then_review",
        "delete_policy": "server_oficina_governed",
        "file_history": "document_versions_plus_syncthing_versioning",
    }
