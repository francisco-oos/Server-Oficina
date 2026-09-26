from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db.models import EvidenceRepository
from app.services.repository_health import (
    reachable_repository_codes,
    record_repository_probe,
)


def _repository(db, prefix: str):
    row = EvidenceRepository(
        code=f"NAS-{prefix}",
        name="NAS prueba",
        repository_type="SMB",
        mount_point=f"/tmp/nas-{prefix}",
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_repository_health_degrades_then_opens_circuit_and_recovers(db):
    prefix = uuid4().hex[:8]
    repository = _repository(db, prefix)
    now = datetime.now(timezone.utc)

    first = record_repository_probe(
        db,
        repository_id=repository.id,
        available=False,
        failure_threshold=3,
        observed_at=now,
    )
    assert first.state == "DEGRADED"
    assert first.consecutive_failures == 1

    second = record_repository_probe(
        db,
        repository_id=repository.id,
        available=False,
        failure_threshold=3,
        observed_at=now + timedelta(seconds=1),
    )
    assert second.state == "DEGRADED"

    third = record_repository_probe(
        db,
        repository_id=repository.id,
        available=False,
        failure_threshold=3,
        observed_at=now + timedelta(seconds=2),
    )
    assert third.state == "OFFLINE"
    assert repository.code not in reachable_repository_codes(
        db,
        observed_at=now + timedelta(seconds=2),
    )

    recovered = record_repository_probe(
        db,
        repository_id=repository.id,
        available=True,
        latency_ms=12,
        observed_at=now + timedelta(seconds=3),
    )
    assert recovered.state == "ONLINE"
    assert recovered.consecutive_failures == 0
    assert repository.code in reachable_repository_codes(
        db,
        observed_at=now + timedelta(seconds=3),
    )


def test_stale_health_is_not_advertised_as_available(db):
    prefix = uuid4().hex[:8]
    repository = _repository(db, prefix)
    old = datetime.now(timezone.utc) - timedelta(minutes=10)

    record_repository_probe(
        db,
        repository_id=repository.id,
        available=True,
        observed_at=old,
    )

    assert repository.code not in reachable_repository_codes(
        db,
        stale_after_seconds=30,
        observed_at=datetime.now(timezone.utc),
    )
