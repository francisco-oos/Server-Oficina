from __future__ import annotations

"""Escaneo incremental de las carpetas canónicas de la Latitude."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, SyncShare
from app.services.document_registry import register_version
from app.services.sync_core import normalize_relative_path

IGNORED_SUFFIXES = {".tmp", ".partial", ".part", ".swp"}


@dataclass(frozen=True)
class FileObservation:
    relative_path: str
    size_bytes: int
    mtime_ns: int


def _ignored(relative: Path) -> bool:
    if any(part in {".stversions", ".stfolder"} for part in relative.parts):
        return True
    if relative.name.startswith("~$"):
        return True
    return relative.suffix.lower() in IGNORED_SUFFIXES


def snapshot(root: Path) -> dict[str, FileObservation]:
    root = root.resolve()
    out: dict[str, FileObservation] = {}
    if not root.exists():
        return out
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _ignored(relative):
            continue
        stat = path.stat()
        rel = normalize_relative_path(relative.as_posix())
        out[rel.casefold()] = FileObservation(rel, stat.st_size, stat.st_mtime_ns)
    return out


def stable_changes(
    previous: dict[str, FileObservation],
    current: dict[str, FileObservation],
) -> list[FileObservation]:
    return [
        item for key, item in current.items()
        if key in previous
        and previous[key].size_bytes == item.size_bytes
        and previous[key].mtime_ns == item.mtime_ns
    ]


def sha256_file(path: Path, *, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def ingest_stable_snapshot(
    db: Session,
    *,
    share: SyncShare,
    root: Path,
    stable: Iterable[FileObservation],
    source_peer_id: str | None = None,
) -> int:
    count = 0
    for observation in stable:
        document = db.scalar(select(DocumentRecord).where(
            DocumentRecord.share_id == share.id,
            DocumentRecord.normalized_path == observation.relative_path.casefold(),
        ))
        latest = None
        if document:
            latest = db.scalar(select(DocumentVersion).where(
                DocumentVersion.document_id == document.id
            ).order_by(DocumentVersion.observed_at.desc()))
        if latest and latest.mtime_ns == observation.mtime_ns and latest.size_bytes == observation.size_bytes:
            continue
        path = (root / observation.relative_path).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError("Archivo fuera de la raíz aprobada") from exc
        digest = sha256_file(path)
        _, _, created = register_version(
            db,
            share=share,
            relative_path=observation.relative_path,
            sha256=digest,
            size_bytes=observation.size_bytes,
            mtime_ns=observation.mtime_ns,
            source_peer_id=source_peer_id,
            change_kind="MODIFIED",
            metadata={"scanner": "stable-two-pass"},
        )
        count += int(created)
    return count


def ingest_missing_documents(
    db: Session,
    *,
    share: SyncShare,
    current: dict[str, FileObservation],
    source_peer_id: str | None = None,
) -> int:
    """Registra tombstones; nunca borra físicamente ni purga versiones."""
    count = 0
    documents = db.scalars(select(DocumentRecord).where(
        DocumentRecord.share_id == share.id,
        DocumentRecord.deleted.is_(False),
    )).all()
    for document in documents:
        if document.normalized_path in current:
            continue
        latest = db.scalar(select(DocumentVersion).where(
            DocumentVersion.document_id == document.id
        ).order_by(DocumentVersion.observed_at.desc()))
        if latest is None or latest.change_kind == "DELETED":
            continue
        _, _, created = register_version(
            db,
            share=share,
            relative_path=document.logical_path,
            sha256=latest.sha256,
            size_bytes=latest.size_bytes,
            mtime_ns=latest.mtime_ns,
            source_peer_id=source_peer_id,
            change_kind="DELETED",
            parent_version_id=latest.id,
            metadata={"scanner": "missing-tombstone", "physical_purge": False},
        )
        count += int(created)
    return count
