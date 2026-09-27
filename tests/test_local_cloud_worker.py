"""Observador Nube Local frente a situaciones del gate físico PC ↔ Latitude.

Estas pruebas reproducen fallos que sólo aparecen con archivos reales en la
carpeta del hub: restaurar un archivo borrado (papelera de Windows o
``.stversions`` conservan mtime), raíz de share ausente/desmontada y un archivo
problemático que no debe detener el observador completo.
"""

import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, SyncShare
from app.services.content_store import ContentStore
from app.services.file_watcher import (
    ingest_missing_documents,
    ingest_stable_snapshot,
    snapshot,
    stable_changes,
)
from app.workers.local_cloud_worker import scan_share


def _share(db, root: Path) -> SyncShare:
    share = SyncShare(
        code=f"LAB-{uuid4().hex[:8]}",
        name="LAB",
        owner_area_code="MATERIAL",
        local_root=str(root),
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share


def _versions(db, share: SyncShare, logical_path: str) -> list[DocumentVersion]:
    document = db.scalar(select(DocumentRecord).where(
        DocumentRecord.share_id == share.id,
        DocumentRecord.logical_path == logical_path,
    ))
    assert document is not None
    return db.scalars(select(DocumentVersion).where(
        DocumentVersion.document_id == document.id
    ).order_by(DocumentVersion.observed_at)).all()


def _ingest(db, share: SyncShare, root: Path, store: ContentStore) -> int:
    first = snapshot(root)
    second = snapshot(root)
    created = ingest_stable_snapshot(
        db, share=share, root=root, stable=stable_changes(first, second), content_store=store
    )
    ingest_missing_documents(db, share=share, current=second)
    return created


def test_restored_file_with_same_mtime_is_recovered_not_left_tombstoned(tmp_path: Path, db):
    """Papelera de Windows / .stversions restauran bytes y mtime originales."""
    root = tmp_path / "share"
    root.mkdir()
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    target = root / "Inventario.xlsx"
    target.write_bytes(b"inventario-v1")
    original = target.stat()

    assert _ingest(db, share, root, store) == 1

    target.unlink()
    _ingest(db, share, root, store)
    document = db.scalar(select(DocumentRecord).where(DocumentRecord.share_id == share.id))
    assert document.deleted is True

    target.write_bytes(b"inventario-v1")
    os.utime(target, ns=(original.st_atime_ns, original.st_mtime_ns))
    assert _ingest(db, share, root, store) == 1

    db.refresh(document)
    assert document.deleted is False
    kinds = [v.change_kind for v in _versions(db, share, "Inventario.xlsx")]
    assert kinds == ["MODIFIED", "DELETED", "RECOVERED"]
    recovered = _versions(db, share, "Inventario.xlsx")[-1]
    assert store.verify(recovered.sha256)


def test_missing_share_root_does_not_tombstone_every_document(tmp_path: Path, db):
    """Un SSD/mount ausente es fallo sistémico, no un borrado masivo."""
    root = tmp_path / "share"
    root.mkdir()
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    for name in ("a.xlsx", "b.docx", "c.pdf"):
        (root / name).write_bytes(name.encode())
    state, stats = scan_share(db, share=share, previous=None, content_store=store, settle_seconds=0)
    assert stats["created_versions"] == 3

    renamed = tmp_path / "share-desmontado"
    root.rename(renamed)
    state, stats = scan_share(db, share=share, previous=state, content_store=store, settle_seconds=0)

    assert stats["deletions"] == 0
    assert stats["unavailable"] == 1
    live = db.scalars(select(DocumentRecord).where(
        DocumentRecord.share_id == share.id, DocumentRecord.deleted.is_(False)
    )).all()
    assert len(live) == 3


def test_empty_share_root_without_syncthing_marker_is_unavailable(tmp_path: Path, db):
    """Un punto de montaje vacío no debe interpretarse como "todo borrado"."""
    root = tmp_path / "share"
    root.mkdir()
    (root / ".stfolder").mkdir()
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    share.syncthing_folder_id = f"lab-{uuid4().hex[:8]}"
    db.commit()
    (root / "a.xlsx").write_bytes(b"a")
    state, stats = scan_share(db, share=share, previous=None, content_store=store, settle_seconds=0)
    assert stats["created_versions"] == 1

    (root / "a.xlsx").unlink()
    (root / ".stfolder").rmdir()
    state, stats = scan_share(db, share=share, previous=state, content_store=store, settle_seconds=0)

    assert stats["unavailable"] == 1
    assert stats["deletions"] == 0


def test_one_unreadable_or_vanished_file_does_not_stop_the_share(tmp_path: Path, db, monkeypatch):
    root = tmp_path / "share"
    root.mkdir()
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    (root / "bueno.xlsx").write_bytes(b"ok")
    (root / "desaparece.xlsx").write_bytes(b"se va durante el hash")

    import app.services.file_watcher as watcher

    real_sha = watcher.sha256_file

    def flaky_sha(path: Path, **kwargs):
        if path.name == "desaparece.xlsx":
            path.unlink()
            raise FileNotFoundError(path)
        return real_sha(path, **kwargs)

    monkeypatch.setattr(watcher, "sha256_file", flaky_sha)
    state, stats = scan_share(db, share=share, previous=None, content_store=store, settle_seconds=0)

    assert stats["created_versions"] == 1
    assert stats["skipped"] == 1
    assert [v.change_kind for v in _versions(db, share, "bueno.xlsx")] == ["MODIFIED"]


def test_case_collision_on_linux_hub_is_quarantined_not_fatal(tmp_path: Path, db):
    """Dos PCs offline crean Radio.xlsx y radio.xlsx: el hub Linux tiene ambos."""
    root = tmp_path / "share"
    root.mkdir()
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    (root / "Radio.xlsx").write_bytes(b"pc1")
    (root / "radio.xlsx").write_bytes(b"pc2")
    (root / "Otro.xlsx").write_bytes(b"otro")

    state, stats = scan_share(db, share=share, previous=None, content_store=store, settle_seconds=0)

    assert stats["created_versions"] == 1
    assert stats["skipped"] == 2
    assert _versions(db, share, "Otro.xlsx")
    names = {d.logical_path for d in db.scalars(select(DocumentRecord).where(
        DocumentRecord.share_id == share.id)).all()}
    assert names == {"Otro.xlsx"}


def test_unchanged_files_are_not_rehashed_every_cycle(tmp_path: Path, db, monkeypatch):
    """Un archivo tocado sin cambiar contenido no debe recalcular SHA cada 5 s."""
    root = tmp_path / "share"
    root.mkdir()
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    target = root / "Grande.bin"
    target.write_bytes(b"x" * 4096)

    import app.services.file_watcher as watcher

    calls: list[str] = []
    real_sha = watcher.sha256_file

    def counting_sha(path: Path, **kwargs):
        calls.append(path.name)
        return real_sha(path, **kwargs)

    monkeypatch.setattr(watcher, "sha256_file", counting_sha)
    state, stats = scan_share(db, share=share, previous=None, content_store=store, settle_seconds=0)
    assert stats["created_versions"] == 1

    stat = target.stat()
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000_000))
    state, _ = scan_share(db, share=share, previous=state, content_store=store, settle_seconds=0)
    state, stats = scan_share(db, share=share, previous=state, content_store=store, settle_seconds=0)
    hashed_after_touch = len(calls)
    for _ in range(5):
        state, stats = scan_share(db, share=share, previous=state, content_store=store, settle_seconds=0)

    assert len(calls) == hashed_after_touch
    assert [v.change_kind for v in _versions(db, share, "Grande.bin")] == ["MODIFIED"]


def test_share_outside_sync_root_is_not_scanned(tmp_path: Path, db):
    sync_root = tmp_path / "files"
    sync_root.mkdir()
    outside = tmp_path / "etc-like"
    outside.mkdir()
    (outside / "secreto.conf").write_bytes(b"no debe archivarse")
    store = ContentStore(tmp_path / "versions")
    share = _share(db, outside)
    messages: list[str] = []

    state, stats = scan_share(
        db, share=share, previous=None, content_store=store, settle_seconds=0,
        allowed_root=sync_root, log=messages.append,
    )
    state, stats = scan_share(
        db, share=share, previous=state, content_store=store, settle_seconds=0,
        allowed_root=sync_root, log=messages.append,
    )

    assert stats["unavailable"] == 1 and stats["created_versions"] == 0
    assert not (tmp_path / "versions").exists() or not any((tmp_path / "versions").rglob("*"))
    assert len(messages) == 1 and "SERVER_OFICINA_SYNC_ROOT" in messages[0]


def test_unavailable_share_recovers_without_tombstones(tmp_path: Path, db):
    root = tmp_path / "share"
    root.mkdir()
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    (root / "a.xlsx").write_bytes(b"a")
    messages: list[str] = []
    state, _ = scan_share(db, share=share, previous=None, content_store=store, settle_seconds=0, log=messages.append)

    hidden = tmp_path / "hidden"
    root.rename(hidden)
    for _ in range(3):
        state, stats = scan_share(db, share=share, previous=state, content_store=store, settle_seconds=0, log=messages.append)
    hidden.rename(root)
    (root / "b.xlsx").write_bytes(b"b")
    state, stats = scan_share(db, share=share, previous=state, content_store=store, settle_seconds=0, log=messages.append)

    assert stats["deletions"] == 0 and stats["created_versions"] == 1
    assert sum("UNAVAILABLE" in m for m in messages) == 1
    assert sum("SHARE_AVAILABLE" in m for m in messages) == 1


def test_stignore_and_stversions_are_not_documents(tmp_path: Path, db):
    root = tmp_path / "share"
    (root / ".stversions" / "sub").mkdir(parents=True)
    (root / ".stversions" / "sub" / "viejo~20260926-120000.xlsx").write_bytes(b"old")
    (root / ".stignore").write_text("(?d)Thumbs.db\n", encoding="utf-8")
    (root / "real.xlsx").write_bytes(b"real")
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)

    state, stats = scan_share(db, share=share, previous=None, content_store=store, settle_seconds=0)

    assert stats["created_versions"] == 1 and stats["skipped"] == 0
    assert set(state.observations) == {"real.xlsx"}


def test_symlink_in_share_is_reported_not_followed(tmp_path: Path, db):
    root = tmp_path / "share"
    root.mkdir()
    outside = tmp_path / "fuera.txt"
    outside.write_bytes(b"fuera de la raiz")
    (root / "enlace.txt").symlink_to(outside)
    (root / "real.xlsx").write_bytes(b"real")
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)

    state, stats = scan_share(db, share=share, previous=None, content_store=store, settle_seconds=0)

    assert stats["created_versions"] == 1 and stats["skipped"] == 1


def test_api_rejects_share_roots_outside_sync_root(client):
    from app.core.config import load_settings
    from tests.helpers import setup_admin

    setup_admin(client)
    sync_root = load_settings().sync_root
    base = {"name": "LAB", "owner_area_code": "MATERIAL"}

    for bad in ("/etc", "relativo/LAB", str(sync_root), str(sync_root / ".." / "fuera")):
        response = client.post("/api/local-cloud/shares", json={
            **base, "code": f"BAD-{uuid4().hex[:6]}", "local_root": bad,
        })
        assert response.status_code == 422, (bad, response.text)

    ok = client.post("/api/local-cloud/shares", json={
        **base, "code": f"LAB-{uuid4().hex[:6]}", "local_root": str(sync_root / "LAB_SYNC"),
    })
    assert ok.status_code == 200, ok.text


def test_worker_runs_as_standalone_process_like_systemd(tmp_path: Path):
    """systemd lanza ``python -m app.workers.local_cloud_worker`` sin importar app.main.

    Antes el proceso aislado caía en el primer archivo con
    ``NoReferencedTableError: ... 'projects'`` porque sólo registraba las tablas
    de Nube Local y no las referenciadas por FK.
    """
    import subprocess
    import sys

    repo = Path(__file__).resolve().parents[1]
    files = tmp_path / "files"
    share = files / "LAB_SYNC"
    share.mkdir(parents=True)
    (share / "Inventario_LAB.xlsx").write_bytes(b"sintetico")
    env = {
        **os.environ,
        "PYTHONPATH": str(repo),
        "PYTHONDONTWRITEBYTECODE": "1",
        "SERVER_OFICINA_DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'so.db'}",
        "SERVER_OFICINA_DATA_DIR": str(tmp_path / "data"),
        "SERVER_OFICINA_SYNC_ROOT": str(files),
        "SERVER_OFICINA_VERSIONS_ROOT": str(tmp_path / "versions"),
    }
    setup = (
        "from app.main import app\n"
        "from app.db.base import Base, SessionLocal, engine\n"
        "from app.db.local_cloud_models import SyncShare\n"
        "Base.metadata.create_all(bind=engine)\n"
        "with SessionLocal() as db:\n"
        f"    db.add(SyncShare(code='LAB', name='LAB', owner_area_code='LAB', local_root={str(share)!r}))\n"
        "    db.commit()\n"
    )
    subprocess.run([sys.executable, "-c", setup], check=True, env=env, cwd=tmp_path)

    worker = subprocess.run(
        [sys.executable, "-m", "app.workers.local_cloud_worker", "--once", "--settle", "0"],
        env=env, cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert worker.returncode == 0, worker.stdout + worker.stderr
    assert "versions=1" in worker.stdout, worker.stdout
    assert any((tmp_path / "versions" / "sha256").rglob("*"))


def test_new_content_after_delete_is_modified_not_recovered(tmp_path: Path, db):
    root = tmp_path / "share"
    root.mkdir()
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    target = root / "Reporte.docx"
    target.write_bytes(b"version-original")
    _ingest(db, share, root, store)
    target.unlink()
    _ingest(db, share, root, store)

    target.write_bytes(b"otro-contenido-en-la-misma-ruta")
    assert _ingest(db, share, root, store) == 1

    assert [v.change_kind for v in _versions(db, share, "Reporte.docx")] == ["MODIFIED", "DELETED", "MODIFIED"]
    document = db.scalar(select(DocumentRecord).where(DocumentRecord.share_id == share.id))
    assert document.deleted is False
