from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db.models import OperationalEvent


def record_event(db: Session, *, entity_type: str, entity_id: str, event_type: str, occurred_at: datetime | None = None, project_id: str | None = None, source_type: str = "SYSTEM", source_id: str | None = None, actor_user_id: str | None = None, payload: dict | None = None) -> OperationalEvent:
    ev = OperationalEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        project_id=project_id,
        source_type=source_type,
        source_id=source_id,
        actor_user_id=actor_user_id,
        payload=payload or {},
    )
    db.add(ev)
    return ev
