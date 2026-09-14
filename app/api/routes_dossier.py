"""API de búsqueda transversal y expedientes por dominio.

Apartado 10 del encargo: hacen falta **las dos** navegaciones. Un usuario de
RRHH trabaja desde RRHH y uno de Material desde Material, pero el sistema
necesita además una búsqueda que cruce áreas.

Buscar ``123456`` puede localizar una persona, un nodo, un radio, un teléfono,
una unidad, un IMEI, un QR, una serie o un número económico. La respuesta indica
qué tipo de ficha corresponde a cada resultado, y cada ficha se sirve con la
estructura de SU dominio: no existe un expediente universal que muestre a una
persona igual que a un nodo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.security import permission_codes
from app.db.base import get_db
from app.db.models import User
from app.services import lookup

router = APIRouter(prefix="/api", tags=["expedientes"])

#: Permiso necesario para abrir cada tipo de ficha. La búsqueda filtra sus
#: resultados con esta misma tabla, de modo que un usuario nunca vea en los
#: resultados algo que después no podría abrir.
DOSSIER_PERMISSION = {
    lookup.DOSSIER_PERSON: "person.view",
    lookup.DOSSIER_NODE: "nodes.view",
    lookup.DOSSIER_ASSET: "assets.view",
    lookup.DOSSIER_TRANSPORT: "transport.view",
}


@router.get("/search")
def cross_search(q: str, db: Session = Depends(get_db), user: User = Depends(require("dashboard.view"))):
    """Búsqueda transversal filtrada por lo que el usuario puede abrir.

    Se exige un mínimo de dos caracteres: con uno solo la consulta devolvería
    prácticamente el padrón completo y sería inútil además de costosa.
    """
    term = q.strip()
    if len(term) < 2:
        raise HTTPException(422, "Ingrese al menos 2 caracteres")
    permissions = permission_codes(user)
    payload = lookup.search(db, term)
    allowed = [
        row for row in payload["results"]
        if DOSSIER_PERMISSION.get(row["dossier"], "") in permissions
    ]
    hidden = len(payload["results"]) - len(allowed)
    return {
        "query": term,
        "count": len(allowed),
        # Se informa cuántas coincidencias se ocultaron por permisos en vez de
        # fingir que no existen: el operador sabe que debe pedir acceso.
        "hidden_by_permissions": hidden,
        "results": allowed,
    }


@router.get("/dossier/person/{person_id}")
def person_dossier(person_id: str, db: Session = Depends(get_db), user: User = Depends(require("person.view"))):
    """Expediente integral de una persona: vida laboral y operativa."""
    dossier = lookup.person_dossier(db, person_id)
    if dossier is None:
        raise HTTPException(404, "Persona no encontrada")
    return dossier


@router.get("/dossier/person/{person_id}/summary")
def person_summary(person_id: str, db: Session = Depends(get_db), user: User = Depends(require("person.view"))):
    """Resumen de localización: estado, grupo, responsable, unidad, radio…"""
    summary = lookup.person_summary(db, person_id)
    if summary is None:
        raise HTTPException(404, "Persona no encontrada")
    return summary


@router.get("/dossier/asset/{asset_id}")
def asset_dossier(asset_id: str, db: Session = Depends(get_db), user: User = Depends(require("assets.view"))):
    """Expediente de un activo, con la estructura propia de su dominio.

    Un activo con capacidad ``node_field`` devuelve la ficha de nodo (ciclo
    operacional, excepciones, línea/estaca); uno con ``transport``, la de
    unidad; el resto, la ficha de activo genérico. El tipo devuelto viaja en
    ``kind`` para que la interfaz elija la plantilla correcta.
    """
    dossier = lookup.build_asset_dossier(db, asset_id)
    if dossier is None:
        raise HTTPException(404, "Activo no encontrado")
    required = DOSSIER_PERMISSION.get(dossier["kind"])
    if required and required not in permission_codes(user):
        raise HTTPException(403, f"Permiso requerido para esta ficha: {required}")
    return dossier
