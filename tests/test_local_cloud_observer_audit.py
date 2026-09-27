"""Auditoría independiente del observador Nube Local (relevo 2026-09-27, segunda ronda).

Cada prueba reproduce un defecto real encontrado leyendo el código integrado:
condiciones de carrera, nombres Unicode, subárboles ilegibles, raíces vacías,
errores de E/S, integridad de la reutilización de hash y espacio en disco.
"""

import errno
import os
import unicodedata
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, SyncShare
from app.services.content_store import ContentStore, sha256_file
from app.workers.local_cloud_worker import scan_share


def _share(db, root: Path, *, syncthing: bool = False) -> SyncShare:
    share = SyncShare(
        code=f"AUD-{uuid4().hex[:8]}", name="Auditoría", owner_area_code="LAB",
        local_root=str(root), syncthing_folder_id=f"aud-{uuid4().hex[:8]}" if syncthing else None,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share


def _versions(db, share: SyncShare) -> list[tuple[str, DocumentVersion]]:
    rows = db.execute(
        select(DocumentRecord.logical_path, DocumentVersion)
        .join(DocumentVersion, DocumentVersion.document_id == DocumentRecord.id)
        .where(DocumentRecord.share_id == share.id)
        .order_by(DocumentVersion.observed_at)
    ).all()
    return [(path, version) for path, version in rows]


def _scan(db, share, state, store, **kwargs):
    return scan_share(db, share=share, previous=state, content_store=store, settle_seconds=0,
                      log=kwargs.pop("log", lambda _m: None), **kwargs)


def test_file_rewritten_between_snapshot_and_hash_never_records_mismatched_size(tmp_path: Path, db, monkeypatch):
    """Carrera: el archivo cambia después de observarse estable y antes del hash."""
    root = tmp_path / "share"
    root.mkdir()
    target = root / "Informe.xlsx"
    target.write_bytes(b"corto")
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)

    import app.services.file_watcher as watcher

    real_sha = watcher.sha256_file
    rewritten = {"done": False}

    def rewrite_then_hash(path: Path, **kwargs):
        if path.name == "Informe.xlsx" and not rewritten["done"]:
            rewritten["done"] = True
            path.write_bytes(b"contenido mucho mas largo escrito durante la ingesta")
        return real_sha(path, **kwargs)

    monkeypatch.setattr(watcher, "sha256_file", rewrite_then_hash)
    state, stats = _scan(db, share, None, store)
    for _ in range(2):
        state, stats = _scan(db, share, state, store)

    versions = _versions(db, share)
    assert versions, "el archivo debe registrarse cuando vuelve a estar estable"
    for _path, version in versions:
        stored = store.path_for(version.sha256)
        assert stored.stat().st_size == version.size_bytes
    assert versions[-1][1].sha256 == sha256_file(target)


def test_decomposed_unicode_name_is_ingested(tmp_path: Path, db):
    """Nombre NFD en disco (macOS, copia manual): la clave lógica es NFC."""
    root = tmp_path / "share"
    root.mkdir()
    nfd = unicodedata.normalize("NFD", "Café Presión.xlsx")
    (root / nfd).write_bytes(b"datos")
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)

    state, stats = _scan(db, share, None, store)

    assert stats["created_versions"] == 1 and stats["skipped"] == 0
    assert [p for p, _ in _versions(db, share)] == [unicodedata.normalize("NFC", "Café Presión.xlsx")]


def test_leading_space_name_is_ingested(tmp_path: Path, db):
    root = tmp_path / "share"
    root.mkdir()
    (root / " espacio inicial.txt").write_bytes(b"x")
    share = _share(db, root)
    state, stats = _scan(db, share, None, ContentStore(tmp_path / "versions"))
    assert stats["created_versions"] == 1


def test_unreadable_subdirectory_does_not_tombstone_its_documents(tmp_path: Path, db, monkeypatch):
    root = tmp_path / "share"
    (root / "Sub").mkdir(parents=True)
    (root / "Sub" / "a.xlsx").write_bytes(b"a")
    (root / "Sub" / "b.xlsx").write_bytes(b"b")
    (root / "raiz.txt").write_bytes(b"r")
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    state, stats = _scan(db, share, None, store)
    assert stats["created_versions"] == 3

    real_scandir = os.scandir
    blocked = str(root / "Sub")

    def denied(path="."):
        if os.fspath(path) == blocked:
            raise PermissionError(errno.EACCES, "Permission denied", blocked)
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", denied)
    state, stats = _scan(db, share, state, store)

    assert stats["deletions"] == 0
    assert stats["skipped"] >= 1
    live = db.scalars(select(DocumentRecord).where(
        DocumentRecord.share_id == share.id, DocumentRecord.deleted.is_(False))).all()
    assert len(live) == 3


def test_io_error_while_walking_share_is_unavailable_not_fatal(tmp_path: Path, db, monkeypatch):
    root = tmp_path / "share"
    root.mkdir()
    (root / "a.xlsx").write_bytes(b"a")
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    state, _ = _scan(db, share, None, store)

    real_scandir = os.scandir

    def io_error(path="."):
        if os.fspath(path) == str(root.resolve()):
            raise OSError(errno.EIO, "Input/output error", str(root))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", io_error)
    state, stats = _scan(db, share, state, store)

    assert stats["unavailable"] == 1 and stats["deletions"] == 0
    assert state.unavailable_code == "ROOT_IO_ERROR"


def test_empty_root_without_syncthing_marker_holds_tombstones(tmp_path: Path, db):
    """Punto de montaje vacío en un share sin marcador: no es borrado masivo."""
    root = tmp_path / "share"
    root.mkdir()
    for name in ("a.xlsx", "b.docx"):
        (root / name).write_bytes(name.encode())
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    state, _ = _scan(db, share, None, store)
    for child in root.iterdir():
        child.unlink()

    state, stats = _scan(db, share, state, store)

    assert stats["deletions"] == 0 and stats["unavailable"] == 1
    assert state.unavailable_code == "ROOT_EMPTY_UNVERIFIED"


def test_emptied_syncthing_folder_with_marker_is_a_real_deletion(tmp_path: Path, db):
    """Con .stfolder presente la carpeta vacía es real: sí hay borrados."""
    root = tmp_path / "share"
    (root / ".stfolder").mkdir(parents=True)
    (root / "a.xlsx").write_bytes(b"a")
    (root / "b.xlsx").write_bytes(b"b")
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root, syncthing=True)
    state, _ = _scan(db, share, None, store)
    (root / "a.xlsx").unlink()
    (root / "b.xlsx").unlink()

    state, stats = _scan(db, share, state, store)

    assert stats["deletions"] == 2 and stats["unavailable"] == 0


def test_root_device_change_is_unavailable(tmp_path: Path, db):
    """Otro filesystem montado (o desmontado) bajo la raíz: no se confía."""
    root = tmp_path / "share"
    root.mkdir()
    (root / "a.xlsx").write_bytes(b"a")
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    state, _ = _scan(db, share, None, store)
    state.root_dev = state.root_dev + 1

    state, stats = _scan(db, share, state, store)

    assert stats["unavailable"] == 1 and stats["deletions"] == 0
    assert state.unavailable_code == "ROOT_DEVICE_CHANGED"


def test_same_size_and_mtime_but_replaced_content_is_detected(tmp_path: Path, db):
    """Integridad: reemplazo con igual tamaño y mtime (nuevo inodo) no se ignora."""
    root = tmp_path / "share"
    root.mkdir()
    target = root / "Tabla.xlsx"
    target.write_bytes(b"AAAA-original")
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    state, _ = _scan(db, share, None, store)
    original = target.stat()

    replacement = root / ".tmp-replace"
    replacement.write_bytes(b"BBBB-cambiado")
    os.utime(replacement, ns=(original.st_atime_ns, original.st_mtime_ns))
    os.replace(replacement, target)
    for _ in range(2):
        state, stats = _scan(db, share, state, store)

    shas = [v.sha256 for _p, v in _versions(db, share)]
    assert shas[-1] == sha256_file(target)
    assert len(shas) == 2


def test_hash_is_reused_after_worker_restart_when_fingerprint_matches(tmp_path: Path, db, monkeypatch):
    root = tmp_path / "share"
    root.mkdir()
    (root / "Grande.bin").write_bytes(b"x" * 8192)
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    _scan(db, share, None, store)

    import app.services.file_watcher as watcher

    calls: list[str] = []
    real_sha = watcher.sha256_file
    monkeypatch.setattr(watcher, "sha256_file", lambda p, **k: calls.append(p.name) or real_sha(p, **k))
    state, stats = _scan(db, share, None, store)  # estado vacío = worker reiniciado

    assert calls == [] and stats["created_versions"] == 0


def test_low_space_in_versions_pauses_archiving_without_failing(tmp_path: Path, db, monkeypatch):
    root = tmp_path / "share"
    root.mkdir()
    (root / "a.xlsx").write_bytes(b"a" * 1024)
    store = ContentStore(tmp_path / "versions", min_free_percent=10)
    share = _share(db, root)

    import app.services.content_store as cs
    from collections import namedtuple

    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(cs.shutil, "disk_usage", lambda _p: usage(1_000_000, 950_000, 50_000))
    messages: list[str] = []
    state, stats = _scan(db, share, None, store, log=messages.append)
    state, stats = _scan(db, share, state, store, log=messages.append)

    assert stats["created_versions"] == 0
    assert sum("STORE_LOW_SPACE" in m for m in messages) == 1

    monkeypatch.setattr(cs.shutil, "disk_usage", lambda _p: usage(1_000_000, 100_000, 900_000))
    state, stats = _scan(db, share, state, store, log=messages.append)
    assert stats["created_versions"] == 1


def test_observer_status_is_visible_in_share_metadata(tmp_path: Path, db):
    root = tmp_path / "share"
    (root / ".stfolder").mkdir(parents=True)
    (root / "Radio.txt").write_bytes(b"1")
    (root / "radio.txt").write_bytes(b"2")
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root, syncthing=True)

    state, _ = _scan(db, share, None, store)
    db.refresh(share)
    observer = share.metadata_json["observer"]
    assert observer["state"] == "AVAILABLE"
    assert observer["issues_total"] == 2

    (root / ".stfolder").rmdir()
    state, _ = _scan(db, share, state, store)
    db.refresh(share)
    assert share.metadata_json["observer"]["state"] == "UNAVAILABLE"
    assert share.metadata_json["observer"]["code"] == "SYNCTHING_MARKER_MISSING"


def test_unexpected_error_in_one_share_does_not_stop_the_others(tmp_path: Path, db, monkeypatch):
    from app.workers import local_cloud_worker as worker

    good_root = tmp_path / "good"
    good_root.mkdir()
    (good_root / "ok.txt").write_bytes(b"ok")
    bad = _share(db, tmp_path / "bad")
    good = _share(db, good_root)
    store = ContentStore(tmp_path / "versions")
    real_scan = worker.scan_share

    def flaky(db_, *, share, **kwargs):
        if share.id == bad.id:
            raise RuntimeError("fallo inesperado")
        return real_scan(db_, share=share, **kwargs)

    monkeypatch.setattr(worker, "scan_share", flaky)
    messages: list[str] = []
    results = {}
    for share in (bad, good):
        results[share.id] = worker.scan_share_isolated(
            db, share=share, previous=None, content_store=store, settle_seconds=0, log=messages.append)

    assert results[good.id][1]["created_versions"] == 1
    assert results[bad.id][1]["errors"] == 1
    assert any("LOCAL_CLOUD_SHARE_ERROR" in m for m in messages)


def test_file_larger_than_headroom_is_deferred_individually(tmp_path: Path, db, monkeypatch):
    root = tmp_path / "share"
    root.mkdir()
    (root / "pequeno.txt").write_bytes(b"p" * 10)
    (root / "grande.bin").write_bytes(b"g" * 5000)
    store = ContentStore(tmp_path / "versions", min_free_percent=10)
    share = _share(db, root)

    import app.services.content_store as cs
    from collections import namedtuple

    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(cs.shutil, "disk_usage", lambda _p: usage(10_000, 7_000, 3_000))
    state, stats = _scan(db, share, None, store)

    assert stats["created_versions"] == 1 and stats["skipped"] == 1
    assert [p for p, _ in _versions(db, share)] == ["pequeno.txt"]


def test_worker_start_removes_orphan_partials_left_by_a_killed_copy(tmp_path: Path):
    """SIGKILL/corte de energía a mitad de archivar deja .partial-* huérfanos."""
    from app.workers.local_cloud_worker import preflight_content_store

    versions = tmp_path / "versions"
    bucket = versions / "sha256" / "ab"
    bucket.mkdir(parents=True)
    orphan = bucket / ".partial-x1y2z3"
    orphan.write_bytes(b"\0" * 4096)
    kept = bucket / ("ab" + "0" * 62)
    kept.write_bytes(b"objeto")

    removed = preflight_content_store(versions)

    assert not orphan.exists() and kept.exists()
    assert removed == 1


def test_history_verifier_detects_missing_corrupt_and_unreferenced(tmp_path: Path, db):
    from app.workers.verify_history import verify_history

    root = tmp_path / "share"
    root.mkdir()
    for name in ("a.txt", "b.txt", "c.txt"):
        (root / name).write_bytes(name.encode() * 10)
    store = ContentStore(tmp_path / "versions")
    share = _share(db, root)
    _scan(db, share, None, store)
    shas = {p: v.sha256 for p, v in _versions(db, share)}
    assert verify_history(db, store, deep=True, share_id=share.id).ok

    store.path_for(shas["a.txt"]).unlink()
    corrupt = store.path_for(shas["b.txt"])
    corrupt.chmod(0o640)
    corrupt.write_bytes(b"x" * corrupt.stat().st_size)
    extra = store.root / "sha256" / "ff" / ("ff" + "1" * 62)
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_bytes(b"huerfano")

    shallow = verify_history(db, store, share_id=share.id)
    assert shallow.missing == [shas["a.txt"]] and shallow.corrupt == []
    report = verify_history(db, store, deep=True, share_id=share.id)
    assert report.missing == [shas["a.txt"]] and report.corrupt == [shas["b.txt"]]
    assert report.exit_code == 4
    assert extra.name in verify_history(db, store).unreferenced
