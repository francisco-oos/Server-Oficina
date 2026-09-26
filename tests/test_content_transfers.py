from uuid import uuid4

import pytest

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, StorageEndpoint, SyncShare
from app.services.content_transfers import begin_transfer, begin_verification, complete_transfer, confirm_offset, pause_transfer, start_or_resume


def _fixture(db, prefix):
    share = SyncShare(code=f"TR-{prefix}", name="Transfer", owner_area_code="GENERAL", local_root=f"/tmp/{prefix}")
    db.add(share); db.flush()
    doc = DocumentRecord(share_id=share.id, owner_area_code="GENERAL", logical_path="evidencia.bin", normalized_path="evidencia.bin")
    db.add(doc); db.flush()
    version = DocumentVersion(document_id=doc.id, sha256="b" * 64, size_bytes=1000, change_kind="MODIFIED")
    endpoint = StorageEndpoint(code=f"NAS-{prefix}", display_name="NAS", endpoint_type="NAS", writable=True, supports_direct_upload=True)
    db.add_all([version, endpoint]); db.commit(); db.refresh(version); db.refresh(endpoint)
    return version, endpoint


def test_interrupted_transfer_resumes_from_confirmed_offset(db):
    prefix = uuid4().hex[:8]
    version, endpoint = _fixture(db, prefix)
    transfer, created = begin_transfer(
        db, transfer_key=f"job-{prefix}", version_id=version.id, destination_endpoint_id=endpoint.id,
        temp_relative_path=".partial/evidencia.bin", final_relative_path="evidencia/evidencia.bin"
    )
    assert created is True
    start_or_resume(db, transfer)
    confirm_offset(db, transfer, 400)
    pause_transfer(db, transfer, error="wifi-lost")
    assert transfer.confirmed_offset == 400
    assert transfer.state == "PAUSED"

    resumed, created_again = begin_transfer(
        db, transfer_key=f"job-{prefix}", version_id=version.id, destination_endpoint_id=endpoint.id,
        temp_relative_path="ignored", final_relative_path="ignored"
    )
    assert created_again is False
    assert resumed.id == transfer.id
    start_or_resume(db, resumed)
    assert resumed.confirmed_offset == 400
    confirm_offset(db, resumed, 1000)
    begin_verification(db, resumed)
    complete_transfer(db, resumed, observed_sha256=version.sha256, observed_size=1000)
    assert resumed.state == "COMPLETED"


def test_transfer_rejects_offset_regression_and_bad_final_hash(db):
    prefix = uuid4().hex[:8]
    version, endpoint = _fixture(db, prefix)
    transfer, _ = begin_transfer(
        db, transfer_key=f"job-{prefix}", version_id=version.id, destination_endpoint_id=endpoint.id,
        temp_relative_path=".partial/a", final_relative_path="a"
    )
    start_or_resume(db, transfer)
    confirm_offset(db, transfer, 700)
    with pytest.raises(ValueError):
        confirm_offset(db, transfer, 699)
    confirm_offset(db, transfer, 1000)
    begin_verification(db, transfer)
    with pytest.raises(ValueError):
        complete_transfer(db, transfer, observed_sha256="c" * 64, observed_size=1000)
