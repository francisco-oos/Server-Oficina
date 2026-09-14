"""API de áreas departamentales y autoridad sobre el dato.

Expone la matriz declarada en ``app/core/areas.py`` para que la interfaz pueda
comunicar quién manda sobre cada dato sin duplicar esa tabla en JavaScript, y
para que la documentación y la pantalla no puedan divergir.

Lectura abierta a cualquier sesión autenticada de forma deliberada: saber *quién
es autoridad* sobre un dato no revela el dato. Poder cambiarlo sí requiere
permisos, y eso se verifica en los endpoints que escriben.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require
from app.core.areas import AREAS, DEFAULT_ROLE_AREAS, authority_matrix, domains_for_area
from app.core.security import permission_codes
from app.db.base import get_db
from app.db.models import Role, RoleArea, User
from app.services.audit import audit
from app.services.dashboards import user_area_codes

router = APIRouter(prefix="/api", tags=["areas"])


class RoleAreaIn(BaseModel):
    area_code: str = Field(min_length=2, max_length=40)


@router.get("/areas")
def list_areas(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Áreas del sistema, marcando las del usuario que consulta."""
    mine = user_area_codes(db, user)
    return [
        {"code": a.code, "name": a.name, "description": a.description, "sort_order": a.sort_order,
         "mine": a.code in mine}
        for a in sorted(AREAS.values(), key=lambda a: a.sort_order)
    ]


@router.get("/areas/authority")
def get_authority_matrix(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Matriz completa: autoridad, consulta, propuesta y confirmación por dominio."""
    mine = sorted(user_area_codes(db, user))
    return {
        "areas": {code: {"name": area.name, "description": area.description} for code, area in AREAS.items()},
        "domains": authority_matrix(),
        "my_areas": mine,
        "my_role_in_domains": {code: domains_for_area(code) for code in mine},
    }


@router.get("/roles/{role_name}/area")
def get_role_area(role_name: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    role = db.scalar(select(Role).where(Role.name == role_name))
    if not role:
        raise HTTPException(404, "Perfil no encontrado")
    link = db.get(RoleArea, role.id)
    area_code = link.area_code if link else DEFAULT_ROLE_AREAS.get(role.name, "GENERAL")
    return {"role": role.name, "area_code": area_code, "area_name": AREAS[area_code].name if area_code in AREAS else area_code,
            "explicit": link is not None}


@router.put("/roles/{role_name}/area")
def set_role_area(role_name: str, data: RoleAreaIn, db: Session = Depends(get_db),
                  user: User = Depends(require("roles.manage"))):
    """Declara el área departamental de un perfil.

    El área no otorga ni retira permisos: agrupa la navegación y permite que la
    vista resumen por departamento tenga sentido. Por eso basta ``roles.manage``
    y no se exige un permiso adicional.
    """
    role = db.scalar(select(Role).where(Role.name == role_name))
    if not role:
        raise HTTPException(404, "Perfil no encontrado")
    area_code = data.area_code.strip().upper()
    if area_code not in AREAS:
        raise HTTPException(422, f"Área desconocida: {area_code}. Válidas: {', '.join(sorted(AREAS))}")
    link = db.get(RoleArea, role.id)
    before = link.area_code if link else None
    if link is None:
        link = RoleArea(role_id=role.id, area_code=area_code)
        db.add(link)
    else:
        link.area_code = area_code
    audit(db, user_id=user.id, action="ROLE_AREA_SET", entity_type="ROLE", entity_id=role.id,
          before={"area_code": before}, after={"area_code": area_code})
    db.commit()
    return {"role": role.name, "area_code": area_code}


@router.get("/me/context")
def my_context(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Contexto operativo del usuario para que la interfaz se adapte a su área.

    Reúne en una sola llamada lo que la UI necesita al arrancar: identidad,
    permisos efectivos, áreas y qué dominios controla, consulta, puede proponer
    o confirmar. Evita que la interfaz tenga que deducir el gobierno del dato.
    """
    areas = sorted(user_area_codes(db, user))
    return {
        "user": {"id": user.id, "username": user.username, "display_name": user.display_name},
        "roles": [r.name for r in user.roles],
        "permissions": sorted(permission_codes(user)),
        "areas": [{"code": c, "name": AREAS[c].name} for c in areas if c in AREAS],
        "domains": {code: domains_for_area(code) for code in areas},
    }
