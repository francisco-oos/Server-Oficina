from uuid import uuid4

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, ExtractedFact, SyncShare
from app.services.knowledge_graph import EntityRef, neighborhood


def test_graph_keeps_document_provenance_on_each_edge(db):
    prefix = uuid4().hex[:8]
    share = SyncShare(code=f"G-{prefix}", name="Grafo", owner_area_code="MATERIAL", local_root=f"/tmp/{prefix}")
    db.add(share); db.flush()
    doc = DocumentRecord(
        share_id=share.id, owner_area_code="MATERIAL",
        logical_path="Material/entregas.xlsx", normalized_path="material/entregas.xlsx",
    )
    db.add(doc); db.flush()
    version = DocumentVersion(document_id=doc.id, sha256="a"*64, size_bytes=100, change_kind="MODIFIED")
    db.add(version); db.flush()
    fact = ExtractedFact(
        source_version_id=version.id, area_code="MATERIAL",
        subject_type="PERSON", subject_id="PACO",
        predicate="CUSTODIES", object_type="ASSET", object_id="R-058",
        confidence=100, status="ACCEPTED",
    )
    db.add(fact); db.commit()

    graph = neighborhood(db, EntityRef("PERSON", "PACO"), depth=1)
    assert {(n["type"], n["id"]) for n in graph["nodes"]} == {("PERSON", "PACO"), ("ASSET", "R-058")}
    edge = graph["edges"][0]
    assert edge["source"]["path"] == "Material/entregas.xlsx"
    assert edge["source"]["sha256"] == "a"*64
