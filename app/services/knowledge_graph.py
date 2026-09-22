from __future__ import annotations

"""Proyección de grafo temporal sobre hechos documentales.

No añade una segunda base de verdad: los nodos/aristas se reconstruyen desde
ExtractedFact y cada arista conserva la versión documental que la respalda.
"""

from collections import deque
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, ExtractedFact


@dataclass(frozen=True)
class EntityRef:
    type: str
    id: str


def neighborhood(db: Session, start: EntityRef, *, depth: int = 2, max_edges: int = 200) -> dict:
    depth = max(0, min(depth, 5))
    queue = deque([(start, 0)])
    seen = {(start.type, start.id)}
    nodes = [{"type": start.type, "id": start.id}]
    edges: list[dict] = []

    while queue and len(edges) < max_edges:
        current, level = queue.popleft()
        if level >= depth:
            continue
        facts = db.scalars(select(ExtractedFact).where(
            ExtractedFact.status.in_(["ACCEPTED", "APPLIED"]),
            or_(
                (ExtractedFact.subject_type == current.type) & (ExtractedFact.subject_id == current.id),
                (ExtractedFact.object_type == current.type) & (ExtractedFact.object_id == current.id),
            ),
        ).order_by(ExtractedFact.occurred_at.desc(), ExtractedFact.observed_at.desc())).all()
        for fact in facts:
            version = db.get(DocumentVersion, fact.source_version_id)
            document = db.get(DocumentRecord, version.document_id) if version else None
            edge = {
                "id": fact.id,
                "from": {"type": fact.subject_type, "id": fact.subject_id},
                "predicate": fact.predicate,
                "to": {"type": fact.object_type, "id": fact.object_id} if fact.object_type and fact.object_id else None,
                "value": fact.value_json,
                "occurred_at": fact.occurred_at.isoformat() if fact.occurred_at else None,
                "area": fact.area_code,
                "confidence": fact.confidence,
                "source": {
                    "version_id": version.id if version else None,
                    "sha256": version.sha256 if version else None,
                    "document_id": document.id if document else None,
                    "path": document.logical_path if document else None,
                },
            }
            edges.append(edge)
            if edge["to"]:
                other = EntityRef(edge["to"]["type"], edge["to"]["id"])
                if (other.type, other.id) not in seen:
                    seen.add((other.type, other.id))
                    nodes.append({"type": other.type, "id": other.id})
                    queue.append((other, level + 1))
            if len(edges) >= max_edges:
                break
    return {"start": {"type": start.type, "id": start.id}, "nodes": nodes, "edges": edges, "truncated": len(edges) >= max_edges}
