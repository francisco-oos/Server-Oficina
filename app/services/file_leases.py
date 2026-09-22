from __future__ import annotations

"""Leases cooperativos para avisar/bloquear una segunda edición en LAN."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import FileLease
from app.services.sync_core import normalize_relative_path


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normaliza fechas de BD a UTC entre SQLite y PostgreSQL."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def active_lease(db: Session, share_id: str, relative_path: str, *, at: datetime | None = None) -> FileLease | None:
    now = _as_utc(at or _now())
    path = normalize_relative_path(relative_path).casefold()
    rows = db.scalars(select(FileLease).where(
        FileLease.share_id == share_id,
        FileLease.normalized_path == path,
        FileLease.status == "ACTIVE",
    ).order_by(FileLease.acquired_at.desc())).all()
    for row in rows:
        if _as_utc(row.expires_at) > now:
            return row
        row.status = "EXPIRED"
    if rows:
        db.commit()
    return None


def acquire_write_lease(
    db: Session, *, share_id: str, relative_path: str, peer_id: str,
    user_id: str | None, ttl_seconds: int = 120,
) -> tuple[FileLease | None, FileLease | None]:
    current = active_lease(db, share_id, relative_path)
    if current and current.peer_id != peer_id:
        return None, current
    now = _now()
    if current:
        current.heartbeat_at = now
        current.expires_at = now + timedelta(seconds=max(30, ttl_seconds))
        current.user_id = user_id or current.user_id
        db.commit()
        db.refresh(current)
        return current, None
    row = FileLease(
        share_id=share_id,
        normalized_path=normalize_relative_path(relative_path).casefold(),
        peer_id=peer_id,
        user_id=user_id,
        mode="WRITE",
        acquired_at=now,
        heartbeat_at=now,
        expires_at=now + timedelta(seconds=max(30, ttl_seconds)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, None


def release_lease(db: Session, lease: FileLease) -> None:
    if lease.status == "ACTIVE":
        lease.status = "RELEASED"
        lease.released_at = _now()
        db.commit()
