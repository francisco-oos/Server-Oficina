from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import PERMISSIONS, ROLE_MAP
from app.db.models import Permission, Role


def ensure_rbac(db: Session) -> None:
    existing = {p.code: p for p in db.scalars(select(Permission)).all()}
    for code, desc in PERMISSIONS.items():
        if code not in existing:
            p = Permission(code=code, description=desc)
            db.add(p)
            existing[code] = p
    db.flush()
    roles = {r.name: r for r in db.scalars(select(Role)).all()}
    for name, codes in ROLE_MAP.items():
        role = roles.get(name)
        if not role:
            role = Role(name=name, description=f"Rol {name}")
            db.add(role)
            db.flush()
        role.permissions = [existing[c] for c in sorted(codes)]
    db.commit()
