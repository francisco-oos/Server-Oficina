from __future__ import annotations

"""API de Nube Local: sincronización, documentos, aprendizaje y grafo."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.db.base import get_db
from app.db.local_cloud_models import (
    DocumentClarification, DocumentRecord, DocumentVersion, FileConflict, FileLease,
    SyncPeer, SyncPeerShare, SyncShare,
)
from app.db.models import User
from app.services.document_learning import answer_clarification
from app.services.document_registry import register_version
from app.services.file_leases import acquire_write_lease, release_lease
from app.services.knowledge_graph import EntityRef, neighborhood
from app.services.sync_core import normalize_relative_path

router = APIRouter(prefix="/api/local-cloud", tags=["nube-local"])


class PeerIn(BaseModel):
    code: str
    display_name: str
    platform: str | None = None
    syncthing_device_id: str | None = None
    trusted: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ShareIn(BaseModel):
    code: str
    name: str
    owner_area_code: str
    local_root: str
    nas_relative_root: str | None = None
    syncthing_folder_id: str | None = None
    delete_policy: str = "ARCHIVE"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PeerShareIn(BaseModel):
    peer_id: str
    share_id: str
    access_mode: str = "READ_WRITE"


class VersionIn(BaseModel):
    share_id: str
    relative_path: str
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)
    mtime_ns: int | None = None
    source_peer_id: str | None = None
    project_id: str | None = None
    document_family: str | None = None
    change_kind: str = "MODIFIED"
    parent_version_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LeaseIn(BaseModel):
    share_id: str
    relative_path: str
    peer_id: str
    ttl_seconds: int = Field(default=120, ge=30, le=1800)


class ClarificationAnswerIn(BaseModel):
    canonical_field: str = Field(min_length=1, max_length=180)
    remember: bool = True


@router.get("/status")
def local_cloud_status(db: Session = Depends(get_db), user: User = Depends(require("localcloud.view"))):
    def count(model, *where):
        stmt = select(func.count()).select_from(model)
        if where:
            stmt = stmt.where(*where)
        return db.scalar(stmt) or 0
    return {
        "peers_active": count(SyncPeer, SyncPeer.active.is_(True)),
        "shares_active": count(SyncShare, SyncShare.active.is_(True)),
        "documents": count(DocumentRecord, DocumentRecord.deleted.is_(False)),
        "versions_pending_analysis": count(DocumentVersion, DocumentVersion.analysis_status == "PENDING"),
        "clarifications_open": count(DocumentClarification, DocumentClarification.status == "OPEN"),
        "leases_active": count(FileLease, FileLease.status == "ACTIVE"),
        "conflicts_open": count(FileConflict, FileConflict.status == "OPEN"),
        "principle": "files_are_canonical_db_is_verifiable_projection",
    }


@router.get("/peers")
def list_peers(db: Session = Depends(get_db), user: User = Depends(require("localcloud.view"))):
    rows = db.scalars(select(SyncPeer).order_by(SyncPeer.display_name)).all()
    return [{"id": x.id, "code": x.code, "display_name": x.display_name, "platform": x.platform,
             "syncthing_device_id": x.syncthing_device_id, "trusted": x.trusted, "active": x.active,
             "last_seen_at": x.last_seen_at, "metadata": x.metadata_json} for x in rows]


@router.post("/peers")
def create_peer(data: PeerIn, db: Session = Depends(get_db), user: User = Depends(require("localcloud.manage"))):
    code = data.code.strip().upper()
    if db.scalar(select(SyncPeer).where(SyncPeer.code == code)):
        raise HTTPException(409, "Ya existe un equipo con ese código")
    row = SyncPeer(code=code, display_name=data.display_name.strip(), platform=data.platform,
                   syncthing_device_id=data.syncthing_device_id, trusted=data.trusted,
                   metadata_json=data.metadata)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "code": row.code}


@router.get("/shares")
def list_shares(db: Session = Depends(get_db), user: User = Depends(require("localcloud.view"))):
    rows = db.scalars(select(SyncShare).order_by(SyncShare.name)).all()
    return [{"id": x.id, "code": x.code, "name": x.name, "owner_area_code": x.owner_area_code,
             "local_root": x.local_root, "nas_relative_root": x.nas_relative_root,
             "syncthing_folder_id": x.syncthing_folder_id, "delete_policy": x.delete_policy,
             "active": x.active, "metadata": x.metadata_json} for x in rows]


@router.post("/shares")
def create_share(data: ShareIn, db: Session = Depends(get_db), user: User = Depends(require("localcloud.manage"))):
    code = data.code.strip().upper()
    if db.scalar(select(SyncShare).where(SyncShare.code == code)):
        raise HTTPException(409, "Ya existe una carpeta lógica con ese código")
    policy = data.delete_policy.strip().upper()
    if policy not in {"ARCHIVE", "REVIEW", "DENY"}:
        raise HTTPException(422, "delete_policy debe ser ARCHIVE, REVIEW o DENY")
    row = SyncShare(code=code, name=data.name.strip(), owner_area_code=data.owner_area_code.strip().upper(),
                    local_root=data.local_root, nas_relative_root=data.nas_relative_root,
                    syncthing_folder_id=data.syncthing_folder_id, delete_policy=policy,
                    metadata_json=data.metadata)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "code": row.code}


@router.post("/peer-shares")
def link_peer_share(data: PeerShareIn, db: Session = Depends(get_db), user: User = Depends(require("localcloud.manage"))):
    if not db.get(SyncPeer, data.peer_id) or not db.get(SyncShare, data.share_id):
        raise HTTPException(404, "Equipo o carpeta no encontrados")
    access = data.access_mode.strip().upper()
    if access not in {"READ_WRITE", "READ_ONLY"}:
        raise HTTPException(422, "access_mode inválido")
    existing = db.scalar(select(SyncPeerShare).where(
        SyncPeerShare.peer_id == data.peer_id, SyncPeerShare.share_id == data.share_id))
    if existing:
        existing.access_mode = access; row = existing
    else:
        row = SyncPeerShare(peer_id=data.peer_id, share_id=data.share_id, access_mode=access); db.add(row)
    db.commit(); db.refresh(row)
    return {"id": row.id, "access_mode": row.access_mode}


@router.post("/document-versions")
def record_document_version(data: VersionIn, db: Session = Depends(get_db), user: User = Depends(require("documents.ingest"))):
    share = db.get(SyncShare, data.share_id)
    if not share or not share.active:
        raise HTTPException(404, "Carpeta lógica no encontrada/activa")
    try:
        path = normalize_relative_path(data.relative_path)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    change = data.change_kind.strip().upper()
    if change not in {"CREATED", "MODIFIED", "DELETED", "MERGED", "RECOVERED"}:
        raise HTTPException(422, "change_kind inválido")
    document, version, created = register_version(
        db, share=share, relative_path=path, sha256=data.sha256, size_bytes=data.size_bytes,
        source_peer_id=data.source_peer_id, source_user_id=user.id, project_id=data.project_id,
        document_family=data.document_family, mtime_ns=data.mtime_ns, change_kind=change,
        parent_version_id=data.parent_version_id, metadata=data.metadata)
    return {"document_id": document.id, "version_id": version.id, "created": created,
            "analysis_status": version.analysis_status, "path": document.logical_path}


@router.get("/documents/{document_id}/versions")
def document_versions(document_id: str, db: Session = Depends(get_db), user: User = Depends(require("localcloud.view"))):
    document = db.get(DocumentRecord, document_id)
    if not document:
        raise HTTPException(404, "Documento no encontrado")
    rows = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == document_id)
                      .order_by(DocumentVersion.observed_at.desc())).all()
    return {"document": {"id": document.id, "path": document.logical_path, "area": document.owner_area_code},
            "versions": [{"id": x.id, "parent_version_id": x.parent_version_id,
                          "merge_parent_version_id": x.merge_parent_version_id, "sha256": x.sha256,
                          "size_bytes": x.size_bytes, "mtime_ns": x.mtime_ns, "change_kind": x.change_kind,
                          "source_peer_id": x.source_peer_id, "observed_at": x.observed_at,
                          "analysis_status": x.analysis_status} for x in rows]}


@router.post("/leases/acquire")
def acquire_lease(data: LeaseIn, db: Session = Depends(get_db), user: User = Depends(require("localcloud.view"))):
    if not db.get(SyncPeer, data.peer_id) or not db.get(SyncShare, data.share_id):
        raise HTTPException(404, "Equipo o carpeta no encontrados")
    try:
        lease, blocking = acquire_write_lease(db, share_id=data.share_id, relative_path=data.relative_path,
                                               peer_id=data.peer_id, user_id=user.id,
                                               ttl_seconds=data.ttl_seconds)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if blocking:
        raise HTTPException(409, {"message": "Archivo reservado por otro equipo", "lease_id": blocking.id,
                                  "peer_id": blocking.peer_id, "user_id": blocking.user_id,
                                  "expires_at": blocking.expires_at.isoformat()})
    return {"lease_id": lease.id, "expires_at": lease.expires_at, "mode": lease.mode}


@router.post("/leases/{lease_id}/release")
def release_lease_endpoint(lease_id: str, db: Session = Depends(get_db), user: User = Depends(require("localcloud.view"))):
    lease = db.get(FileLease, lease_id)
    if not lease:
        raise HTTPException(404, "Reserva no encontrada")
    permissions = {p.code for r in user.roles for p in r.permissions}
    if lease.user_id not in {None, user.id} and "localcloud.manage" not in permissions:
        raise HTTPException(403, "La reserva pertenece a otro usuario")
    release_lease(db, lease)
    return {"released": True}


@router.get("/clarifications")
def open_clarifications(area: str | None = None, db: Session = Depends(get_db),
                        user: User = Depends(require("documents.review"))):
    stmt = select(DocumentClarification).where(DocumentClarification.status == "OPEN")
    if area:
        stmt = stmt.where(DocumentClarification.area_code == area.upper())
    rows = db.scalars(stmt.order_by(DocumentClarification.created_at)).all()
    return [{"id": x.id, "version_id": x.version_id, "area_code": x.area_code,
             "document_family": x.document_family, "raw_label": x.raw_label,
             "question": x.question, "proposal": x.proposal_json, "created_at": x.created_at} for x in rows]


@router.post("/clarifications/{clarification_id}/answer")
def answer_clarification_endpoint(clarification_id: str, data: ClarificationAnswerIn,
                                  db: Session = Depends(get_db),
                                  user: User = Depends(require("documents.review"))):
    row = db.get(DocumentClarification, clarification_id)
    if not row:
        raise HTTPException(404, "Aclaración no encontrada")
    try:
        rule = answer_clarification(db, row, canonical_field=data.canonical_field.strip(),
                                    user_id=user.id, remember=data.remember)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"answered": True, "learning_rule_id": rule.id if rule else None}


@router.get("/graph/{entity_type}/{entity_id}")
def graph_neighborhood(entity_type: str, entity_id: str, depth: int = 2,
                       db: Session = Depends(get_db),
                       user: User = Depends(require("assistant.query"))):
    return neighborhood(db, EntityRef(entity_type.upper(), entity_id), depth=depth)
