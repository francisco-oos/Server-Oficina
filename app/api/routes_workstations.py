from __future__ import annotations

"""API del companion de escritorio: emparejamiento, presencia y auditoría."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.db.base import get_db
from app.db.local_cloud_models import SyncPeer, WorkstationSession
from app.db.models import User
from app.services.workstation_identity import (
    authenticate_peer,
    heartbeat,
    issue_peer_credential,
    login_workstation,
    record_file_event,
)

router = APIRouter(prefix="/api/local-cloud", tags=["companion"])


class WorkstationLoginIn(BaseModel):
    peer_code: str
    username: str
    password: str
    metadata: dict = Field(default_factory=dict)


class WorkstationHeartbeatIn(BaseModel):
    peer_code: str
    session_id: str | None = None


class FileEventIn(BaseModel):
    peer_code: str
    client_event_id: str = Field(min_length=8, max_length=64)
    share_id: str
    action: str
    relative_path: str
    occurred_at: datetime
    session_id: str | None = None
    new_relative_path: str | None = None
    sha256_before: str | None = Field(default=None, min_length=64, max_length=64)
    sha256_after: str | None = Field(default=None, min_length=64, max_length=64)
    size_bytes: int | None = Field(default=None, ge=0)
    metadata: dict = Field(default_factory=dict)


def _peer_or_401(db: Session, peer_code: str, token: str | None) -> SyncPeer:
    peer = authenticate_peer(db, peer_code=peer_code, raw_secret=token or "")
    if not peer:
        raise HTTPException(401, "Credencial de equipo inválida")
    return peer


@router.post("/workstations/{peer_id}/credential")
def rotate_workstation_credential(
    peer_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require("localcloud.manage")),
):
    peer = db.get(SyncPeer, peer_id)
    if not peer:
        raise HTTPException(404, "Equipo no encontrado")
    raw = issue_peer_credential(db, peer)
    return {
        "peer_id": peer.id,
        "peer_code": peer.code,
        "device_token": raw,
        "warning": "Guarde este token en el companion; no vuelve a mostrarse.",
    }


@router.post("/workstations/login")
def workstation_login(
    data: WorkstationLoginIn,
    x_server_oficina_device_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    peer = _peer_or_401(db, data.peer_code, x_server_oficina_device_token)
    try:
        session = login_workstation(
            db,
            peer=peer,
            username=data.username,
            password=data.password,
            metadata=data.metadata,
        )
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    return {
        "session_id": session.id,
        "peer_id": peer.id,
        "user_id": session.user_id,
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "presence_scope": "DIGITAL_WORKSTATION_ONLY",
    }


@router.post("/workstations/heartbeat")
def workstation_heartbeat(
    data: WorkstationHeartbeatIn,
    x_server_oficina_device_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    peer = _peer_or_401(db, data.peer_code, x_server_oficina_device_token)
    return heartbeat(db, peer=peer, session_id=data.session_id)


@router.get("/workstations/active")
def active_workstations(
    db: Session = Depends(get_db),
    user: User = Depends(require("localcloud.view")),
):
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(WorkstationSession).where(
        WorkstationSession.status == "ACTIVE"
    ).order_by(WorkstationSession.last_seen_at.desc())).all()
    result = []
    for row in rows:
        expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
        if expires <= now or row.ended_at:
            continue
        peer = db.get(SyncPeer, row.peer_id)
        operator = db.get(User, row.user_id)
        result.append({
            "session_id": row.id,
            "peer_id": row.peer_id,
            "peer": peer.display_name if peer else None,
            "user_id": row.user_id,
            "user": operator.display_name if operator else None,
            "started_at": row.started_at,
            "last_seen_at": row.last_seen_at,
            "expires_at": row.expires_at,
        })
    return {
        "presence_scope": "DIGITAL_WORKSTATION_ONLY",
        "note": "No sustituye asistencia/estado oficial de RRHH.",
        "items": result,
    }


@router.post("/file-events")
def file_event(
    data: FileEventIn,
    x_server_oficina_device_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    peer = _peer_or_401(db, data.peer_code, x_server_oficina_device_token)
    try:
        event, created = record_file_event(
            db,
            peer=peer,
            client_event_id=data.client_event_id,
            share_id=data.share_id,
            action=data.action,
            relative_path=data.relative_path,
            occurred_at=data.occurred_at,
            session_id=data.session_id,
            new_relative_path=data.new_relative_path,
            sha256_before=data.sha256_before,
            sha256_after=data.sha256_after,
            size_bytes=data.size_bytes,
            metadata=data.metadata,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "event_id": event.id,
        "created": created,
        "attribution": event.attribution,
        "user_id": event.user_id,
    }
