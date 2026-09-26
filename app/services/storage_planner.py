from __future__ import annotations

"""Planificador de ubicación para un archivo antes de mover sus bytes.

La decisión se toma con metadatos (nombre, tamaño, área/familia) y con salud
reciente del repositorio. No abre archivos ni realiza I/O de red. Esto permite
que el Companion sepa si debe usar la capa HOT o esperar/usar NAS_DIRECT sin
provocar una carrera entre dos transportes.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import (
    StoragePolicy,
    StorageRepositoryProfile,
)
from app.db.models import EvidenceRepository
from app.services.repository_health import reachable_repository_codes
from app.services.storage_resolver import choose_storage_policy


@dataclass(frozen=True)
class PlacementPlan:
    mode: str
    repository_code: str | None
    transport_owner: str
    action: str
    reason: str
    pin_local: bool


def plan_content_placement(
    db: Session,
    *,
    filename: str,
    size_bytes: int,
    area_code: str | None = None,
    document_family: str | None = None,
    health_stale_after_seconds: int = 60,
) -> PlacementPlan:
    """Decide el transporte sin inventar disponibilidad ni rutas.

    Estados de salida:
    - SYNCTHING_HOT: el archivo pertenece al namespace HOT replicado.
    - NAS_DIRECT: el Companion puede iniciar una transferencia directa al
      repositorio configurado.
    - KEEP_LOCAL_PENDING_NAS: política NAS_DIRECT válida, pero el destino no
      está actualmente disponible; el archivo se conserva en el nodo origen y
      no se duplica silenciosamente en el hub.
    """
    if size_bytes < 0:
        raise ValueError("size_bytes inválido")

    policies = db.scalars(
        select(StoragePolicy)
        .where(StoragePolicy.active.is_(True))
        .order_by(StoragePolicy.priority, StoragePolicy.code)
    ).all()
    decision = choose_storage_policy(
        policies,
        size_bytes=size_bytes,
        filename=filename,
        area_code=area_code,
        document_family=document_family,
    )

    if decision.mode != "NAS_DIRECT":
        return PlacementPlan(
            mode=decision.mode,
            repository_code=None,
            transport_owner="SYNCTHING",
            action="SYNCTHING_HOT",
            reason=decision.reason,
            pin_local=decision.pin_local,
        )

    code = (decision.repository_code or "").strip()
    if not code:
        return PlacementPlan(
            mode="NAS_DIRECT",
            repository_code=None,
            transport_owner="SERVER_OFICINA",
            action="KEEP_LOCAL_PENDING_NAS",
            reason="nas-direct-policy-without-repository",
            pin_local=True,
        )

    repository = db.scalar(
        select(EvidenceRepository).where(
            EvidenceRepository.code == code,
            EvidenceRepository.active.is_(True),
        )
    )
    if not repository:
        return PlacementPlan(
            mode="NAS_DIRECT",
            repository_code=code,
            transport_owner="SERVER_OFICINA",
            action="KEEP_LOCAL_PENDING_NAS",
            reason="repository-not-active-or-missing",
            pin_local=True,
        )

    profile = db.get(StorageRepositoryProfile, repository.id)
    if (
        profile is None
        or not profile.writable
        or not profile.supports_direct_upload
    ):
        return PlacementPlan(
            mode="NAS_DIRECT",
            repository_code=repository.code,
            transport_owner=profile.transport_owner if profile else "SERVER_OFICINA",
            action="KEEP_LOCAL_PENDING_NAS",
            reason="repository-does-not-support-direct-upload",
            pin_local=True,
        )

    reachable = reachable_repository_codes(
        db,
        stale_after_seconds=health_stale_after_seconds,
    )
    if repository.code not in reachable:
        return PlacementPlan(
            mode="NAS_DIRECT",
            repository_code=repository.code,
            transport_owner=profile.transport_owner,
            action="KEEP_LOCAL_PENDING_NAS",
            reason="repository-not-recently-online",
            pin_local=True,
        )

    return PlacementPlan(
        mode="NAS_DIRECT",
        repository_code=repository.code,
        transport_owner=profile.transport_owner,
        action="NAS_DIRECT",
        reason=decision.reason,
        pin_local=decision.pin_local,
    )
