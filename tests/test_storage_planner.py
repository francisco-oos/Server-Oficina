from datetime import datetime, timezone
from uuid import uuid4

from app.db.local_cloud_models import (
    StoragePolicy,
    StorageRepositoryHealth,
    StorageRepositoryProfile,
)
from app.db.models import EvidenceRepository
from app.services.storage_planner import plan_content_placement


def _nas(db, prefix: str, *, online: bool, direct: bool = True):
    repository = EvidenceRepository(
        code=f"NAS-{prefix}",
        name="NAS prueba",
        repository_type="SMB",
        mount_point=f"/tmp/nas-{prefix}",
        active=True,
    )
    db.add(repository)
    db.flush()
    db.add(StorageRepositoryProfile(
        repository_id=repository.id,
        writable=True,
        supports_direct_upload=direct,
        transport_owner="SERVER_OFICINA",
        direct_upload_mode="RESUMABLE",
    ))
    db.add(StorageRepositoryHealth(
        repository_id=repository.id,
        state="ONLINE" if online else "OFFLINE",
        checked_at=datetime.now(timezone.utc),
        consecutive_failures=0 if online else 3,
    ))
    db.commit()
    db.refresh(repository)
    return repository


def _policy(db, prefix: str, repository_code: str):
    policy = StoragePolicy(
        code=f"LARGE-{prefix}",
        name="Archivos grandes directos a NAS",
        priority=10,
        selector_json={"min_size_bytes": 1_000_000, "extensions": [".bin"]},
        action_json={"mode": "NAS_DIRECT", "repository_code": repository_code},
    )
    db.add(policy)
    db.commit()
    return policy


def test_default_without_policy_stays_in_hot_syncthing_namespace(db):
    plan = plan_content_placement(
        db,
        filename="control.xlsx",
        size_bytes=25_000,
        area_code="MATERIAL",
    )
    assert plan.action == "SYNCTHING_HOT"
    assert plan.transport_owner == "SYNCTHING"
    assert plan.repository_code is None


def test_online_capable_nas_gets_direct_plan(db):
    prefix = uuid4().hex[:8]
    nas = _nas(db, prefix, online=True)
    _policy(db, prefix, nas.code)

    plan = plan_content_placement(
        db,
        filename="video.bin",
        size_bytes=2_000_000,
        area_code="HSE",
    )
    assert plan.action == "NAS_DIRECT"
    assert plan.repository_code == nas.code
    assert plan.transport_owner == "SERVER_OFICINA"


def test_offline_nas_keeps_source_local_instead_of_falling_back_silently(db):
    prefix = uuid4().hex[:8]
    nas = _nas(db, prefix, online=False)
    _policy(db, prefix, nas.code)

    plan = plan_content_placement(
        db,
        filename="video.bin",
        size_bytes=2_000_000,
    )
    assert plan.action == "KEEP_LOCAL_PENDING_NAS"
    assert plan.repository_code == nas.code
    assert plan.pin_local is True
    assert plan.reason == "repository-not-online"


def test_repository_without_direct_upload_never_gets_direct_plan(db):
    prefix = uuid4().hex[:8]
    nas = _nas(db, prefix, online=True, direct=False)
    _policy(db, prefix, nas.code)

    plan = plan_content_placement(
        db,
        filename="video.bin",
        size_bytes=2_000_000,
    )
    assert plan.action == "KEEP_LOCAL_PENDING_NAS"
    assert plan.reason == "repository-does-not-support-direct-upload"
