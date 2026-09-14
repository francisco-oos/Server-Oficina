from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.db.models import OperationalEvent, Person
from app.services.events import record_event


def test_occurred_at_is_distinct_from_recorded_at(db):
    p=Person(full_name='Temporal Persona',normalized_name='TEMPORAL PERSONA');db.add(p);db.flush()
    occurred=datetime.now(timezone.utc)-timedelta(days=3)
    ev=record_event(db,entity_type='PERSON',entity_id=p.id,event_type='LATE_REPORT',occurred_at=occurred,source_type='PHYSICAL_REPORT');db.commit();db.refresh(ev)
    recorded=ev.recorded_at if ev.recorded_at.tzinfo else ev.recorded_at.replace(tzinfo=timezone.utc)
    occurred_db=ev.occurred_at if ev.occurred_at.tzinfo else ev.occurred_at.replace(tzinfo=timezone.utc)
    assert recorded>occurred_db
