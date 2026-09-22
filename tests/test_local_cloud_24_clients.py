from uuid import uuid4

from app.db.local_cloud_models import SyncPeer, SyncShare
from app.services.file_leases import acquire_write_lease, release_lease
from app.services.sync_core import compare_vectors, semantic_three_way_merge


def test_twenty_four_clients_can_coordinate_distinct_files_and_detect_one_collision(db):
    prefix = uuid4().hex[:8]
    share = SyncShare(
        code=f"SIM-{prefix}", name="Simulación 24 clientes", owner_area_code="MATERIAL",
        local_root=f"/tmp/{prefix}", delete_policy="ARCHIVE",
    )
    db.add(share); db.flush()
    peers = []
    for i in range(24):
        peer = SyncPeer(code=f"{prefix}-PC-{i:02d}", display_name=f"PC simulada {i:02d}", platform="WINDOWS")
        db.add(peer); peers.append(peer)
    db.commit()

    leases = []
    for i, peer in enumerate(peers):
        lease, blocking = acquire_write_lease(
            db, share_id=share.id, relative_path=f"Material/archivo-{i:02d}.xlsx",
            peer_id=peer.id, user_id=None, ttl_seconds=120,
        )
        assert lease is not None and blocking is None
        leases.append(lease)

    first, blocking = acquire_write_lease(
        db, share_id=share.id, relative_path="Material/archivo-00.xlsx",
        peer_id=peers[1].id, user_id=None, ttl_seconds=120,
    )
    assert first is None
    assert blocking.peer_id == peers[0].id
    for lease in leases:
        release_lease(db, lease)


def test_24_concurrent_vectors_have_deterministic_conflict_signal():
    vectors = [{f"PC{i:02d}": 1} for i in range(24)]
    concurrent_pairs = 0
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            concurrent_pairs += compare_vectors(vectors[i], vectors[j]).relation == "CONCURRENT"
    assert concurrent_pairs == 276


def test_offline_structured_edits_merge_only_when_fields_do_not_overlap():
    base = [
        {"serial": "N-001", "status": "DEPLOYED", "stake": "1601"},
        {"serial": "N-002", "status": "DEPLOYED", "stake": "1602"},
    ]
    pc_a = [
        {"serial": "N-001", "status": "DAMAGED", "stake": "1601"},
        {"serial": "N-002", "status": "DEPLOYED", "stake": "1602"},
    ]
    pc_b = [
        {"serial": "N-001", "status": "DEPLOYED", "stake": "1601"},
        {"serial": "N-002", "status": "DEPLOYED", "stake": "1605"},
    ]
    result = semantic_three_way_merge(base, pc_a, pc_b, key_field="serial")
    assert result.can_auto_merge
    by_serial = {r["serial"]: r for r in result.merged}
    assert by_serial["N-001"]["status"] == "DAMAGED"
    assert by_serial["N-002"]["stake"] == "1605"
