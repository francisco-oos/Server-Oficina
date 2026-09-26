from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, SyncShare
from app.services.content_store import ContentStore, sha256_file
from app.services.file_watcher import ingest_stable_snapshot, snapshot, stable_changes


def test_content_store_is_content_addressed_and_restorable(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"evidencia-v1")
    store = ContentStore(tmp_path / "versions")

    first = store.archive_file(source)
    second = store.archive_file(source, expected_sha256=first.sha256)

    assert first.created is True
    assert second.created is False
    assert store.verify(first.sha256) is True

    source.unlink()
    restored = store.restore_to(first.sha256, tmp_path / "restored.xlsx")
    assert restored.read_bytes() == b"evidencia-v1"
    assert sha256_file(restored) == first.sha256


def test_watcher_archives_bytes_before_document_version(tmp_path: Path, db):
    prefix = uuid4().hex[:8]
    root = tmp_path / "share"
    root.mkdir()
    file = root / "Entrega.xlsx"
    file.write_bytes(b"version-1")

    share = SyncShare(
        code=f"ARC-{prefix}",
        name="Archivo histórico",
        owner_area_code="MATERIAL",
        local_root=str(root),
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    first = snapshot(root)
    second = snapshot(root)
    store = ContentStore(tmp_path / "versions")

    created = ingest_stable_snapshot(
        db,
        share=share,
        root=root,
        stable=stable_changes(first, second),
        content_store=store,
    )
    assert created == 1

    document = db.scalar(select(DocumentRecord).where(DocumentRecord.share_id == share.id))
    version = db.scalar(select(DocumentVersion).where(DocumentVersion.document_id == document.id))
    assert version.storage_relative_path
    assert store.verify(version.sha256)

    # Borrar el archivo de trabajo no borra la copia histórica.
    file.unlink()
    assert store.verify(version.sha256)
