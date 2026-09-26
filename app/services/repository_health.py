from __future__ import annotations

"""Salud de repositorios físicos con degradación y recuperación explícitas.

La API web no debe bloquearse intentando acceder a un NAS caído. Los probes se
ejecutan fuera del camino crítico y esta tabla conserva el último estado útil.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import StorageRepositoryHealth
from app.db.models import EvidenceRepository


def _utc(value: datetime | None = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def record_repository_probe(
    db: Session,
    *,
    repository_id: str,
    available: bool,
    latency_ms: int | None = None,
    detail: dict | None = None,
    failure_threshold: int = 3,
    observed_at: datetime | None = None,
) -> StorageRepositoryHealth:
    """Registra un probe y aplica un circuit-breaker sencillo y auditable."""
    if failure_threshold < 1:
        raise ValueError("failure_threshold debe ser >= 1")
    repository = db.get(EvidenceRepository, repository_id)
    if not repository:
        raise ValueError("Repositorio no encontrado")

    now = _utc(observed_at)
    row = db.get(StorageRepositoryHealth, repository_id)
    if not row:
        row = StorageRepositoryHealth(repository_id=repository_id)
        db.add(row)

    row.checked_at = now
    row.latency_ms = latency_ms
    row.detail_json = detail or {}

    if available:
        row.state = "ONLINE"
        row.consecutive_failures = 0
        row.last_success_at = now
    else:
        row.consecutive_failures = (row.consecutive_failures or 0) + 1
        row.last_failure_at = now
        row.state = (
            "OFFLINE"
            if row.consecutive_failures >= failure_threshold
            else "DEGRADED"
        )

    db.commit()
    db.refresh(row)
    return row


def reachable_repository_codes(
    db: Session,
    *,
    stale_after_seconds: int = 60,
    observed_at: datetime | None = None,
) -> set[str]:
    """Devuelve sólo repositorios activos con un ONLINE reciente.

    DEGRADED, OFFLINE, UNKNOWN o un probe viejo no se anuncian como disponibles.
    Eso evita que el Content Resolver provoque esperas largas por un NAS caído.
    """
    if stale_after_seconds < 1:
        raise ValueError("stale_after_seconds debe ser >= 1")
    now = _utc(observed_at)
    cutoff = now - timedelta(seconds=stale_after_seconds)

    rows = db.execute(
        select(EvidenceRepository, StorageRepositoryHealth)
        .join(
            StorageRepositoryHealth,
            StorageRepositoryHealth.repository_id == EvidenceRepository.id,
        )
        .where(
            EvidenceRepository.active.is_(True),
            StorageRepositoryHealth.state == "ONLINE",
            StorageRepositoryHealth.checked_at.is_not(None),
            StorageRepositoryHealth.checked_at >= cutoff,
        )
    ).all()
    return {repository.code for repository, _health in rows}
