from __future__ import annotations

"""Registro idempotente de documentos y su DAG de versiones."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, SyncShare
from app.services.sync_path_policy import portable_path_key, validate_portable_office_path


def register_version(
    db: Session,
    *,
    share: SyncShare,
    relative_path: str,
    sha256: str,
    size_bytes: int,
    source_peer_id: str | None = None,
    source_user_id: str | None = None,
    project_id: str | None = None,
    document_family: str | None = None,
    mtime_ns: int | None = None,
    change_kind: str = "MODIFIED",
    parent_version_id: str | None = None,
    storage_relative_path: str | None = None,
    metadata: dict | None = None,
) -> tuple[DocumentRecord, DocumentVersion, bool]:
    path = validate_portable_office_path(relative_path)
    normalized = portable_path_key(path)
    document = db.scalar(select(DocumentRecord).where(
        DocumentRecord.share_id == share.id,
        DocumentRecord.normalized_path == normalized,
    ))
    if document is None:
        document = DocumentRecord(
            share_id=share.id,
            project_id=project_id,
            owner_area_code=share.owner_area_code,
            document_family=document_family,
            logical_path=path,
            normalized_path=normalized,
        )
        db.add(document)
        db.flush()
    elif document_family and not document.document_family:
        document.document_family = document_family

    previous = db.scalar(select(DocumentVersion).where(
        DocumentVersion.document_id == document.id
    ).order_by(DocumentVersion.observed_at.desc()))
    if previous and previous.sha256 == sha256.lower() and previous.change_kind == change_kind.upper():
        return document, previous, False

    if parent_version_id is None:
        parent_version_id = previous.id if previous else None

    version = DocumentVersion(
        document_id=document.id,
        parent_version_id=parent_version_id,
        sha256=sha256.lower(),
        size_bytes=size_bytes,
        mtime_ns=mtime_ns,
        change_kind=change_kind.upper(),
        source_peer_id=source_peer_id,
        source_user_id=source_user_id,
        storage_relative_path=storage_relative_path,
        observed_at=datetime.now(timezone.utc),
        analysis_status="PENDING",
        metadata_json=metadata or {},
    )
    db.add(version)
    if change_kind.upper() == "DELETED":
        document.deleted = True
    else:
        document.deleted = False
    db.commit()
    db.refresh(document)
    db.refresh(version)
    return document, version, True
