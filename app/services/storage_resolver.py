from __future__ import annotations

"""Resolución lógica de contenido y políticas de almacenamiento.

La interfaz y los futuros lectores no deben depender de si los bytes viven en
la PC, la Latitude o un NAS. Este módulo selecciona ubicaciones ya verificadas y
evalúa políticas explícitas. No mueve archivos por sí mismo.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import ContentLocation, DocumentVersion, StorageEndpoint, StoragePolicy


@dataclass(frozen=True)
class ContentResolution:
    version_id: str
    endpoint_code: str | None
    endpoint_type: str | None
    relative_path: str | None
    state: str
    pinned: bool
    reason: str


@dataclass(frozen=True)
class StorageDecision:
    policy_code: str | None
    mode: str
    endpoint_code: str | None
    pin_local: bool
    reason: str


def _matches(selector: dict, *, size_bytes: int, extension: str, area_code: str | None, document_family: str | None) -> bool:
    """Evalúa sólo selectores declarativos simples y auditables."""
    if "min_size_bytes" in selector and size_bytes < int(selector["min_size_bytes"]):
        return False
    if "max_size_bytes" in selector and size_bytes > int(selector["max_size_bytes"]):
        return False

    extensions = {str(x).lower() for x in selector.get("extensions", [])}
    if extensions and extension.lower() not in extensions:
        return False

    areas = {str(x).upper() for x in selector.get("area_codes", [])}
    if areas and (area_code or "").upper() not in areas:
        return False

    families = {str(x) for x in selector.get("document_families", [])}
    if families and (document_family or "") not in families:
        return False

    return True


def choose_storage_policy(
    policies: Iterable[StoragePolicy],
    *,
    size_bytes: int,
    filename: str,
    area_code: str | None = None,
    document_family: str | None = None,
) -> StorageDecision:
    """Selecciona la primera política coincidente por prioridad.

    Si no existe política, el comportamiento seguro es HOT_REPLICATED. Así un
    archivo no desaparece de la capa local sólo por superar un número hardcodeado.
    """
    extension = PurePosixPath(filename).suffix.lower()
    ordered = sorted(
        (p for p in policies if p.active),
        key=lambda p: (p.priority, p.code),
    )
    for policy in ordered:
        selector = policy.selector_json or {}
        if not _matches(
            selector,
            size_bytes=size_bytes,
            extension=extension,
            area_code=area_code,
            document_family=document_family,
        ):
            continue
        action = policy.action_json or {}
        mode = str(action.get("mode", "HOT_REPLICATED")).upper()
        return StorageDecision(
            policy_code=policy.code,
            mode=mode,
            endpoint_code=action.get("endpoint_code"),
            pin_local=bool(action.get("pin_local", False)),
            reason=f"matched:{policy.code}",
        )
    return StorageDecision(
        policy_code=None,
        mode="HOT_REPLICATED",
        endpoint_code=None,
        pin_local=False,
        reason="no-policy-safe-default",
    )


def resolve_version_content(
    db: Session,
    *,
    version_id: str,
    available_endpoint_codes: set[str] | None = None,
) -> ContentResolution:
    """Devuelve la mejor ubicación verificable sin inventar disponibilidad."""
    version = db.get(DocumentVersion, version_id)
    if not version:
        raise ValueError("Versión documental no encontrada")

    rows = db.execute(
        select(ContentLocation, StorageEndpoint)
        .join(StorageEndpoint, StorageEndpoint.id == ContentLocation.endpoint_id)
        .where(
            ContentLocation.version_id == version.id,
            ContentLocation.state == "AVAILABLE",
            StorageEndpoint.active.is_(True),
        )
    ).all()

    candidates: list[tuple[ContentLocation, StorageEndpoint]] = []
    for location, endpoint in rows:
        if available_endpoint_codes is not None and endpoint.code not in available_endpoint_codes:
            continue
        # Una ubicación sólo es elegible si representa exactamente la versión.
        if location.sha256.lower() != version.sha256.lower():
            continue
        if int(location.size_bytes) != int(version.size_bytes):
            continue
        if location.verified_at is None:
            continue
        candidates.append((location, endpoint))

    if not candidates:
        return ContentResolution(
            version_id=version.id,
            endpoint_code=None,
            endpoint_type=None,
            relative_path=None,
            state="UNAVAILABLE",
            pinned=False,
            reason="no-verified-location",
        )

    role_rank = {"PRIMARY": 0, "CACHE": 1, "REPLICA": 2}
    candidates.sort(
        key=lambda pair: (
            0 if pair[0].pinned else 1,
            pair[1].read_priority,
            role_rank.get(pair[0].role, 50),
            pair[1].code,
        )
    )
    location, endpoint = candidates[0]
    return ContentResolution(
        version_id=version.id,
        endpoint_code=endpoint.code,
        endpoint_type=endpoint.endpoint_type,
        relative_path=location.relative_path,
        state="AVAILABLE",
        pinned=location.pinned,
        reason="verified-location",
    )
