from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.core.security import hash_password
from app.db.local_cloud_models import (
    SyncFileEvent,
    SyncPeer,
    SyncPeerShare,
    SyncShare,
    WorkstationSession,
)
from app.db.models import User
from tests.helpers import setup_admin
from app.services.workstation_identity import (
    authenticate_peer,
    issue_peer_credential,
    login_workstation,
    record_file_event,
)


def _operator(db, prefix: str) -> User:
    user = User(
        username=f"op-{prefix}",
        display_name=f"Operador {prefix}",
        password_hash=hash_password("Password123!"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _peer_share(db, prefix: str):
    peer = SyncPeer(code=f"PC-{prefix}", display_name=f"PC {prefix}", platform="WINDOWS")
    share = SyncShare(
        code=f"SH-{prefix}",
        name=f"Share {prefix}",
        owner_area_code="MATERIAL",
        local_root=f"/tmp/{prefix}",
    )
    db.add_all([peer, share])
    db.flush()
    db.add(SyncPeerShare(peer_id=peer.id, share_id=share.id, access_mode="READ_WRITE"))
    db.commit()
    return peer, share


def test_device_credential_is_rotatable_and_never_stored_raw(client, db):
    prefix = uuid4().hex[:8]
    peer, _ = _peer_share(db, prefix)
    raw = issue_peer_credential(db, peer)
    assert raw
    assert authenticate_peer(db, peer_code=peer.code, raw_secret=raw).id == peer.id
    assert authenticate_peer(db, peer_code=peer.code, raw_secret="incorrecto") is None

    rotated = issue_peer_credential(db, peer)
    assert rotated != raw
    assert authenticate_peer(db, peer_code=peer.code, raw_secret=raw) is None
    assert authenticate_peer(db, peer_code=peer.code, raw_secret=rotated).id == peer.id


def test_workstation_login_expires_in_15_days_and_switch_closes_previous(client, db):
    prefix = uuid4().hex[:8]
    peer, _ = _peer_share(db, prefix)
    user1 = _operator(db, prefix + "a")
    user2 = _operator(db, prefix + "b")

    first = login_workstation(
        db, peer=peer, username=user1.username, password="Password123!"
    )
    delta = first.expires_at - first.started_at
    assert timedelta(days=14, hours=23) < delta < timedelta(days=15, hours=1)

    second = login_workstation(
        db, peer=peer, username=user2.username, password="Password123!"
    )
    db.refresh(first)
    assert first.status == "ENDED"
    assert first.ended_at is not None
    assert second.user_id == user2.id


def test_offline_file_events_keep_logs_and_only_attribute_valid_session(client, db):
    prefix = uuid4().hex[:8]
    peer, share = _peer_share(db, prefix)
    user = _operator(db, prefix)
    session = login_workstation(
        db, peer=peer, username=user.username, password="Password123!"
    )

    inside = session.started_at + timedelta(minutes=5)
    e1, created1 = record_file_event(
        db,
        peer=peer,
        client_event_id=f"{prefix}-1",
        share_id=share.id,
        action="MODIFY",
        relative_path="Radios/Entrega.xlsx",
        occurred_at=inside,
        session_id=session.id,
        sha256_after="a" * 64,
    )
    assert created1 is True
    assert e1.attribution == "VERIFIED_USER_DEVICE"
    assert e1.user_id == user.id

    after = session.expires_at + timedelta(minutes=1)
    e2, created2 = record_file_event(
        db,
        peer=peer,
        client_event_id=f"{prefix}-2",
        share_id=share.id,
        action="DELETE",
        relative_path="Radios/Entrega.xlsx",
        occurred_at=after,
        session_id=session.id,
    )
    assert created2 is True
    assert e2.attribution == "DEVICE_ONLY"
    assert e2.user_id is None

    same, created_again = record_file_event(
        db,
        peer=peer,
        client_event_id=f"{prefix}-1",
        share_id=share.id,
        action="MODIFY",
        relative_path="Radios/Entrega.xlsx",
        occurred_at=inside,
        session_id=session.id,
    )
    assert created_again is False
    assert same.id == e1.id
    assert db.scalar(select(SyncFileEvent).where(SyncFileEvent.client_event_id == f"{prefix}-1")).id == e1.id


def test_valid_15_day_login_is_not_equal_to_online_presence(client, db):
    prefix = uuid4().hex[:8]
    peer, _ = _peer_share(db, prefix)
    operator = _operator(db, prefix)
    session = login_workstation(
        db, peer=peer, username=operator.username, password="Password123!"
    )
    # La sesión sigue autenticada, pero un heartbeat viejo no significa
    # "persona actualmente en la oficina".
    session.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    db.commit()

    setup_admin(client)
    response = client.get("/api/local-cloud/workstations/active")
    assert response.status_code == 200, response.text
    item = next(x for x in response.json()["items"] if x["session_id"] == session.id)
    assert item["session_valid"] is True
    assert item["online"] is False
    assert item["presence_state"] == "SESSION_VALID_OFFLINE"
