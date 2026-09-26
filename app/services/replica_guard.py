from __future__ import annotations

"""Guardas para liberar caché sin convertir la optimización en pérdida de datos.

Inspirado en el principio de git-annex de no eliminar una copia cuando no se
pueden verificar las réplicas mínimas exigidas. Este módulo sólo decide; la
eliminación física pertenece a un worker posterior y auditado.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import ContentLocation, DocumentVersion, StorageEndpoint


@dataclass(frozen=True)
class EvictionDecision:
    allowed: bool
    verified_copies_after: int
    required_copies: int
    missing_required_endpoints: tuple[str, ...]
    reason: str


def can_evict_location(
    db: Session,
    *,
    location_id: str,
    min_verified_copies: int = 1,
    required_endpoint_codes: set[str] | None = None,
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
        select(ContentLocation, StorageEndpoint)
        .join(StorageEndpoint, StorageEndpoint.id == ContentLocation.endpoint_id)
        .where(
            ContentLocation.version_id == version.id,
            ContentLocation.state == "AVAILABLE",
            ContentLocation.id != candidate.id,
            StorageEndpoint.active.is_(True),
        )
    ).all()

    safe = []
    for location, endpoint in rows:
        if location.verified_at is None:
            continue
        if location.sha256.lower() != version.sha256.lower():
            continue
        if int(location.size_bytes) != int(version.size_bytes):
            continue
        safe.append((location, endpoint))

    endpoint_codes = {endpoint.code for _, endpoint in safe}
    required = {x for x in (required_endpoint_codes or set()) if x}
    missing = tuple(sorted(required - endpoint_codes))
    enough = len(safe) >= min_verified_copies
    allowed = enough and not missing

    if missing:
        reason = "missing-required-endpoints"
    elif not enough:
        reason = "insufficient-verified-copies"
    else:
        reason = "safe-to-evict"

    return EvictionDecision(
        allowed=allowed,
        verified_copies_after=len(safe),
        required_copies=min_verified_copies,
        missing_required_endpoints=missing,
        reason=reason,
    )
