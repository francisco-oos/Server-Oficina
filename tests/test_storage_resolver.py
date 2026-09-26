from datetime import datetime, timezone
from uuid import uuid4

from app.db.local_cloud_models import ContentLocation, DocumentRecord, DocumentVersion, StorageEndpoint, StoragePolicy, SyncShare
from app.services.storage_resolver import choose_storage_policy, resolve_version_content


def _version(db, prefix: str):
    share = SyncShare(code=f"ST-{prefix}", name="Storage", owner_area_code="GENERAL", local_root=f"/tmp/{prefix}")
    db.add(share); db.flush()
    doc = DocumentRecord(share_id=share.id, owner_area_code="GENERAL", logical_path="Video/evidencia.mp4", normalized_path="video/evidencia.mp4")
    db.add(doc); db.flush()
    version = DocumentVersion(document_id=doc.id, sha256="a" * 64, size_bytes=2_000_000_000, change_kind="MODIFIED")
    db.add(version); db.commit(); db.refresh(version)
    return version


def test_storage_policy_has_no_hardcoded_large_file_threshold(db):
    decision = choose_storage_policy([], size_bytes=20_000_000_000, filename="evidencia.mp4", area_code="HSE")
    assert decision.mode == "HOT_REPLICATED"
    assert decision.policy_code is None
    prefix = uuid4().hex[:8]
    policy = StoragePolicy(code=f"LARGE-{prefix}", name="Videos grandes al NAS", priority=10, selector_json={"min_size_bytes": 1_000_000_000, "extensions": [".mp4"]}, action_json={"mode": "NAS_DIRECT", "endpoint_code": "NAS-OFICINA"})
    db.add(policy); db.commit()
    decision = choose_storage_policy([policy], size_bytes=2_000_000_000, filename="evidencia.mp4", area_code="HSE")
    assert decision.mode == "NAS_DIRECT"
    assert decision.endpoint_code == "NAS-OFICINA"


def test_resolver_prefers_verified_pinned_location(db):
    prefix = uuid4().hex[:8]
    version = _version(db, prefix)
    hub = StorageEndpoint(code=f"HUB-{prefix}", display_name="Latitude", endpoint_type="HUB", read_priority=10)
    nas = StorageEndpoint(code=f"NAS-{prefix}", display_name="NAS", endpoint_type="NAS", read_priority=20)
    db.add_all([hub, nas]); db.flush()
    now = datetime.now(timezone.utc)
    db.add_all([
        ContentLocation(version_id=version.id, endpoint_id=hub.id, relative_path="sha256/aa/a", role="CACHE", state="AVAILABLE", sha256=version.sha256, size_bytes=version.size_bytes, verified_at=now),
        ContentLocation(version_id=version.id, endpoint_id=nas.id, relative_path="evidencias/evidencia.mp4", role="PRIMARY", state="AVAILABLE", sha256=version.sha256, size_bytes=version.size_bytes, pinned=True, verified_at=now),
    ])
    db.commit()
    result = resolve_version_content(db, version_id=version.id)
    assert result.state == "AVAILABLE"
    assert result.endpoint_code == nas.code
    assert result.pinned is True


def test_resolver_never_claims_unverified_content(db):
    prefix = uuid4().hex[:8]
    version = _version(db, prefix)
    nas = StorageEndpoint(code=f"NAS-{prefix}", display_name="NAS", endpoint_type="NAS")
    db.add(nas); db.flush()
    db.add(ContentLocation(version_id=version.id, endpoint_id=nas.id, relative_path="evidencia.mp4", role="PRIMARY", state="AVAILABLE", sha256=version.sha256, size_bytes=version.size_bytes, verified_at=None))
    db.commit()
    result = resolve_version_content(db, version_id=version.id)
    assert result.state == "UNAVAILABLE"
    assert result.endpoint_code is None
