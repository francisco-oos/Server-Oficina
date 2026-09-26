from datetime import datetime, timezone
from uuid import uuid4

from app.db.local_cloud_models import ContentLocation, DocumentRecord, DocumentVersion, StorageEndpoint, SyncShare
from app.services.replica_guard import can_evict_location


def _setup(db, prefix):
    share = SyncShare(code=f"RG-{prefix}", name="Guard", owner_area_code="GENERAL", local_root=f"/tmp/{prefix}")
    db.add(share); db.flush()
    doc = DocumentRecord(share_id=share.id, owner_area_code="GENERAL", logical_path="archivo.bin", normalized_path="archivo.bin")
    db.add(doc); db.flush()
    version = DocumentVersion(document_id=doc.id, sha256="d" * 64, size_bytes=1234, change_kind="MODIFIED")
    hub = StorageEndpoint(code=f"HUB-{prefix}", display_name="Hub", endpoint_type="HUB")
    nas = StorageEndpoint(code=f"NAS-{prefix}", display_name="NAS", endpoint_type="NAS")
    db.add_all([version, hub, nas]); db.flush()
    now = datetime.now(timezone.utc)
    local = ContentLocation(version_id=version.id, endpoint_id=hub.id, relative_path="cache/a", role="CACHE", state="AVAILABLE", sha256=version.sha256, size_bytes=version.size_bytes, verified_at=now)
    remote = ContentLocation(version_id=version.id, endpoint_id=nas.id, relative_path="archive/a", role="PRIMARY", state="AVAILABLE", sha256=version.sha256, size_bytes=version.size_bytes, verified_at=now)
    db.add_all([local, remote]); db.commit(); db.refresh(local); db.refresh(remote)
    return version, hub, nas, local, remote


def test_eviction_allowed_only_when_another_verified_copy_exists(db):
    prefix = uuid4().hex[:8]
    _, _, nas, local, remote = _setup(db, prefix)
    decision = can_evict_location(db, location_id=local.id, min_verified_copies=1, required_endpoint_codes={nas.code})
    assert decision.allowed is True
    assert decision.verified_copies_after == 1

    remote.verified_at = None
    db.commit()
    blocked = can_evict_location(db, location_id=local.id, min_verified_copies=1, required_endpoint_codes={nas.code})
    assert blocked.allowed is False
    assert blocked.reason == "missing-required-endpoints"


def test_eviction_refuses_when_copy_count_would_fall_below_policy(db):
    prefix = uuid4().hex[:8]
    _, _, _, local, _ = _setup(db, prefix)
    decision = can_evict_location(db, location_id=local.id, min_verified_copies=2)
    assert decision.allowed is False
    assert decision.verified_copies_after == 1
    assert decision.reason == "insufficient-verified-copies"
