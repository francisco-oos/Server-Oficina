from __future__ import annotations

"""Máquina de estados para transferencias reanudables de contenido.

El servicio no conoce SMB, Synology ni HTTP. Sólo gobierna idempotencia,
offset confirmado y promoción tras verificación. Cada adapter implementa el
transporte físico sin duplicar estas reglas.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import ContentTransfer, DocumentVersion, StorageEndpoint


ACTIVE_STATES = {"PENDING", "TRANSFERRING", "PAUSED", "FAILED"}


def begin_transfer(
    db: Session,
    *,
    transfer_key: str,
    version_id: str,
    destination_endpoint_id: str,
    temp_relative_path: str,
    final_relative_path: str,
    source_endpoint_id: str | None = None,
    metadata: dict | None = None,
) -> tuple[ContentTransfer, bool]:
    """Crea o recupera una sesión usando una clave idempotente."""
    key = transfer_key.strip()
    if not key:
        raise ValueError("transfer_key requerido")
    existing = db.scalar(select(ContentTransfer).where(ContentTransfer.transfer_key == key))
    if existing:
        if existing.version_id != version_id or existing.destination_endpoint_id != destination_endpoint_id:
            raise ValueError("transfer_key reutilizada para otro destino o versión")
        return existing, False

    version = db.get(DocumentVersion, version_id)
    endpoint = db.get(StorageEndpoint, destination_endpoint_id)
    if not version or not endpoint or not endpoint.active or not endpoint.writable:
        raise ValueError("Versión o endpoint destino no disponible para escritura")

    row = ContentTransfer(
        transfer_key=key,
        version_id=version.id,
        source_endpoint_id=source_endpoint_id,
        destination_endpoint_id=endpoint.id,
        state="PENDING",
        expected_sha256=version.sha256.lower(),
        total_bytes=version.size_bytes,
        confirmed_offset=0,
        temp_relative_path=temp_relative_path,
        final_relative_path=final_relative_path,
        metadata_json=metadata or {},
    )
    db.add(row); db.commit(); db.refresh(row)
    return row, True


def start_or_resume(db: Session, transfer: ContentTransfer) -> ContentTransfer:
    if transfer.state == "COMPLETED":
        return transfer
    if transfer.state == "VERIFYING":
        # Tras un reinicio se reanuda la verificación, no se retransmiten bytes.
        return transfer
    if transfer.state not in ACTIVE_STATES:
        raise ValueError("Estado de transferencia no reanudable")
    if transfer.confirmed_offset < 0 or transfer.confirmed_offset > transfer.total_bytes:
        raise ValueError("Offset persistido inválido")
    transfer.state = "TRANSFERRING"
    transfer.attempt_count += 1
    transfer.last_error = None
    db.commit(); db.refresh(transfer)
    return transfer


def confirm_offset(db: Session, transfer: ContentTransfer, new_offset: int) -> ContentTransfer:
    """El offset nunca retrocede ni puede superar el tamaño esperado."""
    if transfer.state not in {"TRANSFERRING", "PAUSED"}:
        raise ValueError("Transferencia no acepta avance de offset")
    if new_offset < transfer.confirmed_offset:
        raise ValueError("El offset confirmado no puede retroceder")
    if new_offset > transfer.total_bytes:
        raise ValueError("El offset supera el tamaño esperado")
    transfer.confirmed_offset = new_offset
    db.commit(); db.refresh(transfer)
    return transfer


def pause_transfer(db: Session, transfer: ContentTransfer, *, error: str | None = None) -> ContentTransfer:
    if transfer.state == "COMPLETED":
        return transfer
    transfer.state = "PAUSED"
    transfer.last_error = error
    db.commit(); db.refresh(transfer)
    return transfer


def begin_verification(db: Session, transfer: ContentTransfer) -> ContentTransfer:
    if transfer.confirmed_offset != transfer.total_bytes:
        raise ValueError("No se puede verificar una transferencia incompleta")
    transfer.state = "VERIFYING"
    db.commit(); db.refresh(transfer)
    return transfer


def complete_transfer(
    db: Session,
    transfer: ContentTransfer,
    *,
    observed_sha256: str,
    observed_size: int,
) -> ContentTransfer:
    if transfer.state != "VERIFYING":
        raise ValueError("La transferencia debe estar en VERIFYING")
    if observed_size != transfer.total_bytes:
        raise ValueError("Tamaño final no coincide")
    if observed_sha256.lower() != transfer.expected_sha256.lower():
        raise ValueError("SHA-256 final no coincide")
    transfer.state = "COMPLETED"
    transfer.completed_at = datetime.now(timezone.utc)
    transfer.last_error = None
    db.commit(); db.refresh(transfer)
    return transfer
