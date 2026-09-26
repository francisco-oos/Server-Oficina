from __future__ import annotations

"""Resolución lógica de contenido y políticas de almacenamiento.

La interfaz y los futuros lectores no deben depender de si los bytes viven en
la PC, la Latitude o un NAS. EvidenceRepository conserva la identidad única del
almacenamiento; esta capa sólo evalúa política y disponibilidad verificada.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import (
    ContentLocation,
    DocumentVersion,
    StoragePolicy,
    StorageRepositoryProfile,
)
from app.db.models import EvidenceRepository


@dataclass(frozen=True)
class ContentResolution:
    version_id: str
    repository_code: str | None
    repository_type: str | None
    relative_path: str | None
    state: str
    pinned: bool
    reason: str


@dataclass(frozen=True)
class StorageDecision:
    policy_code: str | None
    mode: str
    repository_code: str | None
    pin_local: bool
    reason: str


def _matches(
    selector: dict,
    *,
    size_bytes: int,
    extension: str,
    area_code: str | None,
    document_family: str | None,
) -> bool:
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

    Sin política explícita se conserva el comportamiento seguro HOT_REPLICATED.
    No existe un umbral de tamaño mágico incrustado en el código.
    """
    extension = PurePosixPath(filename).suffix.lower()
    ordered = sorted(
        (policy for policy in policies if policy.active),
        key=lambda policy: (policy.priority, policy.code),
    )
    for policy in ordered:
        if not _matches(
            policy.selector_json or {},
            size_bytes=size_bytes,
            extension=extension,
            area_code=area_code,
            document_family=document_family,
        ):
            continue
        action = policy.action_json or {}
        return StorageDecision(
            policy_code=policy.code,
            mode=str(action.get("mode", "HOT_REPLICATED")).upper(),
            repository_code=action.get("repository_code"),
            pin_local=bool(action.get("pin_local", False)),
            reason=f"matched:{policy.code}",
        )

    return StorageDecision(
        policy_code=None,
        mode="HOT_REPLICATED",
        repository_code=None,
        pin_local=False,
        reason="no-policy-safe-default",
    )


def resolve_version_content(
    db: Session,
    *,
    version_id: str,
    available_repository_codes: set[str] | None = None,
) -> ContentResolution:
    """Devuelve la mejor ubicación verificada sin inventar disponibilidad."""
    version = db.get(DocumentVersion, version_id)
    if not version:
        raise ValueError("Versión documental no encontrada")

    rows = db.execute(
        select(ContentLocation, EvidenceRepository, StorageRepositoryProfile)
        .join(
            EvidenceRepository,
            EvidenceRepository.id == ContentLocation.repository_id,
        )
        .outerjoin(
            StorageRepositoryProfile,
            StorageRepositoryProfile.repository_id == EvidenceRepository.id,
        )
        .where(
            ContentLocation.version_id == version.id,
            ContentLocation.state == "AVAILABLE",
            EvidenceRepository.active.is_(True),
        )
    ).all()

    candidates: list[
        tuple[ContentLocation, EvidenceRepository, StorageRepositoryProfile | None]
    ] = []
    for location, repository, profile in rows:
        if (
            available_repository_codes is not None
            and repository.code not in available_repository_codes
        ):
            continue
        if location.sha256.lower() != version.sha256.lower():
            continue
        if int(location.size_bytes) != int(version.size_bytes):
            continue
        if location.verified_at is None:
            continue
        candidates.append((location, repository, profile))

    if not candidates:
        return ContentResolution(
            version_id=version.id,
            repository_code=None,
            repository_type=None,
            relative_path=None,
            state="UNAVAILABLE",
            pinned=False,
            reason="no-verified-location",
        )

    role_rank = {"PRIMARY": 0, "CACHE": 1, "REPLICA": 2}
    # Menor read_priority = origen preferido. Un pin sólo desempata dentro de
    # prioridades equivalentes; nunca obliga a preferir un NAS sobre una copia
    # local ya verificada.
    candidates.sort(
        key=lambda pair: (
            pair[2].read_priority if pair[2] is not None else 100,
            0 if pair[0].pinned else 1,
            role_rank.get(pair[0].role, 50),
            pair[1].code,
        )
    )

    location, repository, _profile = candidates[0]
    return ContentResolution(
        version_id=version.id,
        repository_code=repository.code,
        repository_type=repository.repository_type,
        relative_path=location.relative_path,
        state="AVAILABLE",
        pinned=location.pinned,
        reason="verified-location",
    )
