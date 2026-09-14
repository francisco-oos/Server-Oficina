from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def audit(db: Session, *, user_id: str | None, action: str, entity_type: str, entity_id: str | None = None, before=None, after=None, ip_address: str | None = None) -> None:
    db.add(AuditLog(user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id, before=before, after=after, ip_address=ip_address))
