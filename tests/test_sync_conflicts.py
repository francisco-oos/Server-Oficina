from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, SyncShare
from app.services.content_store import ContentStore
from app.services.file_watcher import ingest_stable_snapshot, snapshot, stable_changes
from app.services.sync_conflicts import parse_syncthing_conflict_path


def test_parse_syncthing_conflict_name():
    parsed = parse_syncthing_conflict_path(
        "Material/Entrega.sync-conflict-20260926-101530-ABCDEFG.xlsx"
    )
    assert parsed is not None
    assert parsed.original_path == "Material/Entrega.xlsx"
    assert parsed.modified_by == "ABCDEFG"


def test_conflict_copy_is_archived_but_blocked_from_normal_analysis(tmp_path: Path, db):
    prefix = uuid4().hex[:8]
    root = tmp_path / "share"
    root.mkdir()
    conflict = root / "Inventario.sync-conflict-20260926-101530-PC01.xlsx"
    conflict.write_bytes(b"version-conflictiva")

    share = SyncShare(
        code=f"CF-{prefix}",
        name="Conflictos",
        owner_area_code="MATERIAL",
        local_root=str(root),
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    first = snapshot(root)
    second = snapshot(root)
    store = ContentStore(tmp_path / "versions")
    assert ingest_stable_snapshot(
        db,
        share=share,
        root=root,
        stable=stable_changes(first, second),
        content_store=store,
    ) == 1

    document = db.scalar(select(DocumentRecord).where(DocumentRecord.share_id == share.id))
    version = db.scalar(select(DocumentVersion).where(DocumentVersion.document_id == document.id))
    assert document.metadata_json["syncthing_conflict"] is True
    assert document.metadata_json["conflict_of"] == "Inventario.xlsx"
    assert version.change_kind == "CONFLICT"
    assert version.analysis_status == "CONFLICT_REVIEW"
    assert store.verify(version.sha256)
