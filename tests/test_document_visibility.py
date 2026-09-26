from uuid import uuid4

from sqlalchemy import select

from app.core.security import hash_password
from app.db.local_cloud_models import DocumentRecord, DocumentVersion, SyncShare
from app.db.models import Role, User
from tests.helpers import setup_admin


def test_office_user_can_follow_documents_from_multiple_owner_areas(client, db):
    setup_admin(client)
    prefix = uuid4().hex[:8]
    role = db.scalar(select(Role).where(Role.name == "OFFICE"))
    user = User(username=f"office-{prefix}", display_name="Oficina transversal", password_hash=hash_password("StrongPass123!"), roles=[role])
    db.add(user)

    shares = []
    for area in ("RRHH", "MATERIAL"):
        share = SyncShare(code=f"{area[:3]}-{prefix}", name=f"{area} docs", owner_area_code=area, local_root=f"/tmp/{prefix}/{area}")
        db.add(share); db.flush()
        doc = DocumentRecord(share_id=share.id, owner_area_code=area, logical_path=f"{area}/control-{area.lower()}.xlsx", normalized_path=f"{area.lower()}/control-{area.lower()}.xlsx")
        db.add(doc); db.flush()
        db.add(DocumentVersion(document_id=doc.id, sha256=("a" if area == "RRHH" else "b") * 64, size_bytes=100, change_kind="MODIFIED"))
        shares.append(share)
    db.commit()

    client.post("/api/auth/logout")
    login = client.post("/api/auth/login", json={"username": user.username, "password": "StrongPass123!"})
    assert login.status_code == 200, login.text

    result = client.get("/api/local-cloud/documents")
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["visibility"] == "TRANSVERSAL_AUTHORIZED_OFFICE"
    areas = {x["owner_area_code"] for x in payload["items"] if prefix in x["path"] or "control-" in x["path"]}
    assert {"RRHH", "MATERIAL"}.issubset(areas)

    only_material = client.get("/api/local-cloud/documents", params={"area": "MATERIAL"})
    assert only_material.status_code == 200
    assert all(x["owner_area_code"] == "MATERIAL" for x in only_material.json()["items"])
