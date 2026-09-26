from __future__ import annotations

"""Persistencia aditiva para Nube Local, ingesta documental y grafo temporal.

Estas tablas NO reemplazan Tracking Core. Guardan transporte/sincronización,
versiones documentales, aprendizaje aprobado y hechos extraídos con procedencia.
El grafo es una proyección consultable y reconstruible; los documentos originales
y los eventos de dominio siguen siendo la evidencia autoritativa.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def uid() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class SyncPeer(Base):
    __tablename__ = "sync_peers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(180))
    platform: Mapped[str | None] = mapped_column(String(80), nullable=True)
    syncthing_device_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    trusted: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SyncShare(Base):
    __tablename__ = "sync_shares"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    owner_area_code: Mapped[str] = mapped_column(String(40), index=True)
    local_root: Mapped[str] = mapped_column(Text)
    nas_relative_root: Mapped[str | None] = mapped_column(Text, nullable=True)
    syncthing_folder_id: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    delete_policy: Mapped[str] = mapped_column(String(30), default="ARCHIVE")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SyncPeerShare(Base):
    __tablename__ = "sync_peer_shares"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    peer_id: Mapped[str] = mapped_column(ForeignKey("sync_peers.id", ondelete="CASCADE"), index=True)
    share_id: Mapped[str] = mapped_column(ForeignKey("sync_shares.id", ondelete="CASCADE"), index=True)
    access_mode: Mapped[str] = mapped_column(String(30), default="READ_WRITE")
    __table_args__ = (UniqueConstraint("peer_id", "share_id", name="uq_sync_peer_share"),)


class DocumentRecord(Base):
    __tablename__ = "document_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    share_id: Mapped[str] = mapped_column(ForeignKey("sync_shares.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    owner_area_code: Mapped[str] = mapped_column(String(40), index=True)
    document_family: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    logical_path: Mapped[str] = mapped_column(Text)
    normalized_path: Mapped[str] = mapped_column(Text, index=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("share_id", "normalized_path", name="uq_document_share_path"),)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("document_records.id", ondelete="CASCADE"), index=True)
    parent_version_id: Mapped[str | None] = mapped_column(ForeignKey("document_versions.id"), nullable=True, index=True)
    merge_parent_version_id: Mapped[str | None] = mapped_column(ForeignKey("document_versions.id"), nullable=True, index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    mtime_ns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    change_kind: Mapped[str] = mapped_column(String(30), default="MODIFIED")
    storage_relative_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_peer_id: Mapped[str | None] = mapped_column(ForeignKey("sync_peers.id"), nullable=True, index=True)
    source_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    stable_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DocumentLearningRule(Base):
    __tablename__ = "document_learning_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    area_code: Mapped[str] = mapped_column(String(40), index=True)
    document_family: Mapped[str] = mapped_column(String(100), index=True)
    normalized_label: Mapped[str] = mapped_column(String(180), index=True)
    canonical_field: Mapped[str] = mapped_column(String(180), index=True)
    context_signature: Mapped[str] = mapped_column(String(64), default="", index=True)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (
        UniqueConstraint(
            "area_code", "document_family", "normalized_label", "context_signature",
            name="uq_document_learning_rule",
        ),
    )


class DocumentClarification(Base):
    __tablename__ = "document_clarifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    version_id: Mapped[str | None] = mapped_column(ForeignKey("document_versions.id"), nullable=True, index=True)
    area_code: Mapped[str] = mapped_column(String(40), index=True)
    document_family: Mapped[str] = mapped_column(String(100), index=True)
    raw_label: Mapped[str] = mapped_column(String(180))
    normalized_label: Mapped[str] = mapped_column(String(180), index=True)
    context_signature: Mapped[str] = mapped_column(String(64), default="", index=True)
    question: Mapped[str] = mapped_column(Text)
    proposal_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    answer_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ExtractedFact(Base):
    __tablename__ = "extracted_facts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), index=True)
    area_code: Mapped[str] = mapped_column(String(40), index=True)
    subject_type: Mapped[str] = mapped_column(String(60), index=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    predicate: Mapped[str] = mapped_column(String(100), index=True)
    object_type: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    object_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(30), default="PROPOSED", index=True)
    applied_event_id: Mapped[str | None] = mapped_column(ForeignKey("operational_events.id"), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class FileLease(Base):
    __tablename__ = "file_leases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    share_id: Mapped[str] = mapped_column(ForeignKey("sync_shares.id", ondelete="CASCADE"), index=True)
    normalized_path: Mapped[str] = mapped_column(Text, index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("document_records.id"), nullable=True, index=True)
    peer_id: Mapped[str] = mapped_column(ForeignKey("sync_peers.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), default="WRITE")
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FileConflict(Base):
    __tablename__ = "file_conflicts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("document_records.id", ondelete="CASCADE"), index=True)
    base_version_id: Mapped[str | None] = mapped_column(ForeignKey("document_versions.id"), nullable=True)
    left_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), index=True)
    right_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    conflict_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resolution_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)



class SyncPeerCredential(Base):
    """Credencial de emparejamiento del companion; sólo se persiste el hash."""

    __tablename__ = "sync_peer_credentials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    peer_id: Mapped[str] = mapped_column(ForeignKey("sync_peers.id", ondelete="CASCADE"), unique=True, index=True)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkstationSession(Base):
    """Quién está usando una PC; no equivale al estado laboral oficial de RRHH."""

    __tablename__ = "workstation_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    peer_id: Mapped[str] = mapped_column(ForeignKey("sync_peers.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SyncFileEvent(Base):
    """Evento de archivo enviado por el companion con idempotencia por UUID."""

    __tablename__ = "sync_file_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    client_event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    peer_id: Mapped[str] = mapped_column(ForeignKey("sync_peers.id", ondelete="CASCADE"), index=True)
    workstation_session_id: Mapped[str | None] = mapped_column(ForeignKey("workstation_sessions.id"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    share_id: Mapped[str] = mapped_column(ForeignKey("sync_shares.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(30), index=True)
    normalized_path: Mapped[str] = mapped_column(Text, index=True)
    new_normalized_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256_before: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sha256_after: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    attribution: Mapped[str] = mapped_column(String(30), default="DEVICE_ONLY", index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)



class StorageEndpoint(Base):
    """Ubicación física intercambiable capaz de almacenar contenido documental.

    El endpoint NO es la identidad del documento. Puede ser el SSD del hub, un
    NAS/Synology u otro backend futuro. Las decisiones de tamaño/caché viven en
    StoragePolicy y no se hardcodean en el servicio.
    """

    __tablename__ = "storage_endpoints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(180))
    endpoint_type: Mapped[str] = mapped_column(String(40), index=True)
    root_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    writable: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_direct_upload: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_range_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_priority: Mapped[int] = mapped_column(Integer, default=100)
    write_priority: Mapped[int] = mapped_column(Integer, default=100)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ContentLocation(Base):
    """Ubicación verificable de los bytes de una DocumentVersion."""

    __tablename__ = "content_locations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), index=True)
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("storage_endpoints.id", ondelete="CASCADE"), index=True)
    relative_path: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30), default="REPLICA", index=True)
    state: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (
        UniqueConstraint(
            "version_id", "endpoint_id", "relative_path",
            name="uq_content_location_version_endpoint_path",
        ),
    )


class StoragePolicy(Base):
    """Regla configurable de ubicación/caché; evita umbrales mágicos en código."""

    __tablename__ = "storage_policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    selector_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    action_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
