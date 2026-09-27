"""Atribución técnica de dispositivo sin Companion (``modifiedBy`` de Syncthing)."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, SyncPeer, SyncShare
from app.services.content_store import ContentStore
from app.services.syncthing_attribution import SyncthingAttributor, short_device_id
from app.workers.local_cloud_worker import scan_share

PC1_ID = "LX7RWCU-ABCDEFG-HIJKLMN-OPQRSTU-VWXYZ23-4567ABC-DEFGHIJ-KLMNOPQ"


class FakeSyncthing:
    def __init__(self, entries: dict[str, dict] | None = None, fail: bool = False):
        self.entries = entries or {}
        self.fail = fail
        self.calls = 0

    def file_info(self, *, folder: str, relative_path: str) -> dict:
        self.calls += 1
        if self.fail:
            raise ConnectionRefusedError("syncthing caído")
        return {"local": self.entries[relative_path]}


def _setup(db, tmp_path: Path, name: str, data: bytes):
    root = tmp_path / "share"
    (root / ".stfolder").mkdir(parents=True)
    target = root / name
    target.write_bytes(data)
    share = SyncShare(code=f"ATR-{uuid4().hex[:8]}", name="Atribución", owner_area_code="LAB",
                      local_root=str(root), syncthing_folder_id=f"atr-{uuid4().hex[:8]}")
    peer = SyncPeer(code=f"PC-{uuid4().hex[:6]}", display_name="PC LAB", platform="windows",
                    syncthing_device_id=f"{uuid4().hex[:7].upper()}-{PC1_ID[8:]}")
    db.add_all([share, peer])
    db.commit()
    return root, target, share, peer


def _entry(target: Path, short: str, **override) -> dict:
    stat = target.stat()
    modified = datetime.fromtimestamp(stat.st_mtime_ns / 1e9, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return {"modifiedBy": short, "size": stat.st_size, "modified": modified, **override}


def _latest(db, share) -> DocumentVersion:
    return db.scalars(select(DocumentVersion).join(DocumentRecord).where(
        DocumentRecord.share_id == share.id).order_by(DocumentVersion.observed_at.desc())).first()


def test_short_device_id_matches_syncthing_format():
    assert short_device_id(PC1_ID) == "LX7RWCU"
    assert short_device_id(PC1_ID.lower()) == "LX7RWCU"


def test_version_is_attributed_to_the_device_that_modified_it(tmp_path: Path, db):
    root, target, share, peer = _setup(db, tmp_path, "Inventario.xlsx", b"datos")
    short = short_device_id(peer.syncthing_device_id)
    client = FakeSyncthing({"Inventario.xlsx": _entry(target, short)})
    attributor = SyncthingAttributor(client, folder_id=share.syncthing_folder_id,
                                     peers_by_short_id={short: (peer.id, peer.code)})

    scan_share(db, share=share, previous=None, content_store=ContentStore(tmp_path / "v"),
               settle_seconds=0, log=lambda _m: None, attribute=attributor)

    version = _latest(db, share)
    assert version.source_peer_id == peer.id
    attribution = version.metadata_json["attribution"]
    assert attribution["scope"] == "DEVICE" and attribution["person"] is None
    assert attribution["verified"] is True and attribution["peer_code"] == peer.code


def test_mismatched_syncthing_metadata_is_recorded_as_unverified(tmp_path: Path, db):
    root, target, share, peer = _setup(db, tmp_path, "Nota.txt", b"hola")
    short = short_device_id(peer.syncthing_device_id)
    client = FakeSyncthing({"Nota.txt": _entry(target, short, size=999)})
    attributor = SyncthingAttributor(client, folder_id=share.syncthing_folder_id,
                                     peers_by_short_id={short: (peer.id, peer.code)})

    scan_share(db, share=share, previous=None, content_store=ContentStore(tmp_path / "v"),
               settle_seconds=0, log=lambda _m: None, attribute=attributor)

    assert _latest(db, share).metadata_json["attribution"]["verified"] is False


def test_syncthing_api_down_never_blocks_ingest_and_is_not_retried_per_file(tmp_path: Path, db):
    root, target, share, peer = _setup(db, tmp_path, "a.txt", b"a")
    (root / "b.txt").write_bytes(b"b")
    client = FakeSyncthing(fail=True)
    messages: list[str] = []
    attributor = SyncthingAttributor(client, folder_id=share.syncthing_folder_id,
                                     peers_by_short_id={}, log=messages.append)

    state, stats = scan_share(db, share=share, previous=None, content_store=ContentStore(tmp_path / "v"),
                              settle_seconds=0, log=messages.append, attribute=attributor)

    assert stats["created_versions"] == 2
    assert client.calls == 1
    assert _latest(db, share).metadata_json["attribution"]["method"] == "none"
    assert sum("ATTRIBUTION_UNAVAILABLE" in m for m in messages) == 1


def test_unknown_device_keeps_short_id_without_inventing_a_peer(tmp_path: Path, db):
    root, target, share, peer = _setup(db, tmp_path, "x.txt", b"x")
    client = FakeSyncthing({"x.txt": _entry(target, "ZZZZZZZ")})
    attributor = SyncthingAttributor(client, folder_id=share.syncthing_folder_id, peers_by_short_id={})

    scan_share(db, share=share, previous=None, content_store=ContentStore(tmp_path / "v"),
               settle_seconds=0, log=lambda _m: None, attribute=attributor)

    version = _latest(db, share)
    assert version.source_peer_id is None
    assert version.metadata_json["attribution"]["device_short_id"] == "ZZZZZZZ"
    assert version.metadata_json["attribution"]["peer_code"] is None


def test_file_not_yet_indexed_by_syncthing_does_not_disable_attribution(tmp_path: Path, db):
    from urllib.error import HTTPError

    root, target, share, peer = _setup(db, tmp_path, "nuevo.txt", b"n")
    (root / "otro.txt").write_bytes(b"o")
    short = short_device_id(peer.syncthing_device_id)

    class PartlyIndexed(FakeSyncthing):
        def file_info(self, *, folder, relative_path):
            self.calls += 1
            if relative_path == "nuevo.txt":
                raise HTTPError("http://127.0.0.1:8384/rest/db/file", 404, "Not Found", {}, None)
            return {"local": _entry(root / relative_path, short)}

    client = PartlyIndexed()
    attributor = SyncthingAttributor(client, folder_id=share.syncthing_folder_id,
                                     peers_by_short_id={short: (peer.id, peer.code)})
    scan_share(db, share=share, previous=None, content_store=ContentStore(tmp_path / "v"),
               settle_seconds=0, log=lambda _m: None, attribute=attributor)

    assert client.calls == 2 and attributor.disabled_reason is None
    by_path = dict(db.execute(select(DocumentRecord.logical_path, DocumentVersion.metadata_json)
                              .join(DocumentVersion).where(DocumentRecord.share_id == share.id)).all())
    assert by_path["nuevo.txt"]["attribution"]["verified"] is False
    assert by_path["otro.txt"]["attribution"]["verified"] is True
