from __future__ import annotations

"""Identidad persistente de las PCs y atribución humana de eventos de archivo.

La presencia digital indica qué usuario de Server Oficina opera una PC. No debe
interpretarse como estado laboral oficial de RRHH. Las sesiones expiran por
política (15 días por defecto) y un cambio de operador cierra la sesión previa.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import load_settings
from app.core.security import verify_password
from app.db.local_cloud_models import (
    SyncFileEvent,
    SyncPeer,
    SyncPeerCredential,
    SyncPeerShare,
    SyncShare,
    WorkstationSession,
)
from app.db.models import User
from app.services.sync_path_policy import portable_path_key


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_peer_credential(db: Session, peer: SyncPeer) -> str:
    """Rota la credencial del companion y devuelve el secreto una sola vez."""
    now = datetime.now(timezone.utc)
    existing = db.scalar(select(SyncPeerCredential).where(SyncPeerCredential.peer_id == peer.id))
    if existing:
        existing.active = False
        existing.revoked_at = now
        db.flush()
        # Un peer mantiene una sola fila por restricción UNIQUE; la reutilizamos.
        raw = secrets.token_urlsafe(48)
        existing.secret_hash = _hash_secret(raw)
        existing.active = True
        existing.created_at = now
        existing.revoked_at = None
        db.commit()
        return raw

    raw = secrets.token_urlsafe(48)
    db.add(SyncPeerCredential(peer_id=peer.id, secret_hash=_hash_secret(raw), active=True))
    db.commit()
    return raw


def authenticate_peer(db: Session, *, peer_code: str, raw_secret: str) -> SyncPeer | None:
    peer = db.scalar(select(SyncPeer).where(
        SyncPeer.code == peer_code.strip().upper(),
        SyncPeer.active.is_(True),
        SyncPeer.trusted.is_(True),
    ))
    if not peer or not raw_secret:
        return None
    credential = db.scalar(select(SyncPeerCredential).where(
        SyncPeerCredential.peer_id == peer.id,
        SyncPeerCredential.active.is_(True),
    ))
    if not credential:
        return None
    if not hmac.compare_digest(credential.secret_hash, _hash_secret(raw_secret)):
        return None
    return peer


def login_workstation(
    db: Session,
    *,
    peer: SyncPeer,
    username: str,
    password: str,
    metadata: dict | None = None,
) -> WorkstationSession:
    user = db.scalar(select(User).where(User.username == username.strip().lower()))
    if not user or not user.active or not verify_password(password, user.password_hash):
        raise ValueError("Credenciales inválidas")

    now = datetime.now(timezone.utc)
    current = db.scalars(select(WorkstationSession).where(
        WorkstationSession.peer_id == peer.id,
        WorkstationSession.status == "ACTIVE",
    )).all()
    for row in current:
        row.status = "ENDED"
        row.ended_at = now

    days = max(1, load_settings().workstation_session_days)
    session = WorkstationSession(
        peer_id=peer.id,
        user_id=user.id,
        started_at=now,
        expires_at=now + timedelta(days=days),
        last_seen_at=now,
        metadata_json=metadata or {},
    )
    peer.last_seen_at = now
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def heartbeat(db: Session, *, peer: SyncPeer, session_id: str | None) -> dict:
    now = datetime.now(timezone.utc)
    peer.last_seen_at = now
    session = db.get(WorkstationSession, session_id) if session_id else None
    valid = False
    if session and session.peer_id == peer.id and session.status == "ACTIVE":
        expires = _utc(session.expires_at)
        ended = _utc(session.ended_at) if session.ended_at else None
        valid = expires > now and ended is None
        if valid:
            session.last_seen_at = now
        else:
            session.status = "EXPIRED"
    db.commit()
    return {
        "peer_id": peer.id,
        "session_id": session.id if session else None,
        "session_valid": valid,
        "requires_reauth": not valid,
        "expires_at": session.expires_at if session else None,
    }


_ALLOWED_ACTIONS = {"CREATE", "MODIFY", "DELETE", "RENAME", "OPEN", "CLOSE", "CONFLICT"}


def record_file_event(
    db: Session,
    *,
    peer: SyncPeer,
    client_event_id: str,
    share_id: str,
    action: str,
    relative_path: str,
    occurred_at: datetime,
    session_id: str | None = None,
    new_relative_path: str | None = None,
    sha256_before: str | None = None,
    sha256_after: str | None = None,
    size_bytes: int | None = None,
    metadata: dict | None = None,
) -> tuple[SyncFileEvent, bool]:
    """Registra una operación idempotente sin perder eventos offline.

    Si el evento ocurrió dentro de una sesión humana válida, se atribuye al
    usuario. Si no, se conserva como DEVICE_ONLY y la auditoría no se pierde.
    """
    existing = db.scalar(select(SyncFileEvent).where(SyncFileEvent.client_event_id == client_event_id))
    if existing:
        return existing, False

    share = db.get(SyncShare, share_id)
    if not share:
        raise ValueError("Carpeta no encontrada")
    link = db.scalar(select(SyncPeerShare).where(
        SyncPeerShare.peer_id == peer.id,
        SyncPeerShare.share_id == share.id,
    ))
    if not link:
        raise ValueError("La PC no está autorizada para esa carpeta")

    action = action.strip().upper()
    if action not in _ALLOWED_ACTIONS:
        raise ValueError("Acción de archivo inválida")
    if action == "RENAME" and not new_relative_path:
        raise ValueError("RENAME requiere ruta destino")

    occurred = _utc(occurred_at)
    session = db.get(WorkstationSession, session_id) if session_id else None
    user_id = None
    attribution = "DEVICE_ONLY"
    if session and session.peer_id == peer.id:
        start = _utc(session.started_at)
        end = _utc(session.ended_at) if session.ended_at else _utc(session.expires_at)
        expiry = _utc(session.expires_at)
        valid_until = min(end, expiry)
        if start <= occurred <= valid_until:
            user_id = session.user_id
            attribution = "VERIFIED_USER_DEVICE"

    event = SyncFileEvent(
        client_event_id=client_event_id,
        peer_id=peer.id,
        workstation_session_id=session.id if session and session.peer_id == peer.id else None,
        user_id=user_id,
        share_id=share.id,
        action=action,
        normalized_path=portable_path_key(relative_path),
        new_normalized_path=portable_path_key(new_relative_path) if new_relative_path else None,
        sha256_before=sha256_before.lower() if sha256_before else None,
        sha256_after=sha256_after.lower() if sha256_after else None,
        size_bytes=size_bytes,
        occurred_at=occurred,
        attribution=attribution,
        metadata_json=metadata or {},
    )
    peer.last_seen_at = datetime.now(timezone.utc)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event, True
