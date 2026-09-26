from __future__ import annotations

"""Guardas para liberar caché sin convertir la optimización en pérdida de datos.

Inspirado en el principio de git-annex de no eliminar una copia cuando no se
pueden verificar las réplicas mínimas exigidas. Este módulo sólo decide; la
eliminación física pertenece a un worker posterior y auditado.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import ContentLocation, DocumentVersion
from app.db.models import EvidenceRepository


@dataclass(frozen=True)
class EvictionDecision:
    allowed: bool
    verified_copies_after: int
    required_copies: int
    missing_required_repositories: tuple[str, ...]
    reason: str


def can_evict_location(
    db: Session,
    *,
    location_id: str,
    min_verified_copies: int = 1,
    required_repository_codes: set[str] | None = None,
) -> EvictionDecision:
    """Comprueba seguridad usando únicamente ubicaciones verificadas distintas.

    La ubicación candidata deja de contar antes de evaluar la política. Esto
    evita que una caché se borre creyendo que ella misma es la réplica segura.
    """
    if min_verified_copies < 1:
        raise ValueError("min_verified_copies debe ser >= 1")

    candidate = db.get(ContentLocation, location_id)
    if not candidate:
        raise ValueError("Ubicación de contenido no encontrada")
    version = db.get(DocumentVersion, candidate.version_id)
    if not version:
        raise ValueError("Versión documental no encontrada")

    rows = db.execute(
        select(ContentLocation, EvidenceRepository)
        .join(EvidenceRepository, EvidenceRepository.id == ContentLocation.repository_id)
        .where(
            ContentLocation.version_id == version.id,
            ContentLocation.state == "AVAILABLE",
            ContentLocation.id != candidate.id,
            EvidenceRepository.active.is_(True),
        )
    ).all()

    # Varias rutas del mismo endpoint NO son réplicas independientes. Para
    # seguridad contamos como máximo una copia verificada por repositorio físico.
    safe_by_repository: dict[str, tuple[ContentLocation, EvidenceRepository]] = {}
    for location, repository in rows:
        if location.verified_at is None:
            continue
        if location.sha256.lower() != version.sha256.lower():
            continue
        if int(location.size_bytes) != int(version.size_bytes):
            continue
        safe_by_repository.setdefault(repository.id, (location, repository))

    repository_codes = {repository.code for _, repository in safe_by_repository.values()}
    required = {x for x in (required_repository_codes or set()) if x}
    missing = tuple(sorted(required - repository_codes))
    enough = len(safe_by_repository) >= min_verified_copies
    allowed = enough and not missing

    if missing:
        reason = "missing-required-repositories"
    elif not enough:
        reason = "insufficient-verified-copies"
    else:
        reason = "safe-to-evict"

    return EvictionDecision(
        allowed=allowed,
        verified_copies_after=len(safe_by_repository),
        required_copies=min_verified_copies,
        missing_required_repositories=missing,
        reason=reason,
    )
