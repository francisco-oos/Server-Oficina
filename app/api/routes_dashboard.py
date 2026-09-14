"""API de la Vista Resumen configurable y del modo DEV.

Dos audiencias distintas comparten este módulo:

* **Operador.** ``GET /api/dashboards`` y ``GET /api/dashboards/{key}`` le dan
  su vista resumen ya filtrada por permisos y perfil. Nunca ve un widget cuyo
  permiso no tiene, aunque el administrador lo haya colocado en su dashboard.

* **Administrador DEV.** ``/api/dev/widgets`` y ``/api/dev/dashboards/...`` le
  permiten mostrar, ocultar, ordenar, redimensionar, retitular y restringir
  widgets, además de crear dashboards por departamento. Todo bajo el permiso
  ``dashboard.configure``.

El endpoint heredado ``GET /api/dashboard`` (alpha.2/alpha.3) sigue existiendo
en ``app/api/routes.py`` y no se toca: hay instalaciones y pruebas que dependen
de su forma. Ver ``docs/30_DASHBOARD_CONFIGURABLE_Y_WIDGETS.md``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.areas import AREAS
from app.db.base import get_db
from app.db.models import DashboardDefinition, DashboardWidgetPlacement, Role, User
from app.services import dashboards as dashboard_service
from app.services import widgets as widget_registry
from app.services.audit import audit

router = APIRouter(prefix="/api", tags=["dashboards"])


class PlacementIn(BaseModel):
    """Una colocación de widget dentro de un dashboard."""

    widget_key: str = Field(min_length=1, max_length=100)
    visible: bool = True
    position: int | None = None
    size: str | None = None
    title_override: str | None = None
    #: Restringe a perfiles concretos. Nunca amplía: el permiso del widget manda.
    role_names: list[str] = Field(default_factory=list)
    options: dict = Field(default_factory=dict)


class LayoutIn(BaseModel):
    placements: list[PlacementIn]


class DashboardIn(BaseModel):
    key: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    description: str = ""
    area_code: str = "GENERAL"
    sort_order: int = 100


class DashboardPatchIn(BaseModel):
    name: str | None = None
    description: str | None = None
    area_code: str | None = None
    sort_order: int | None = None
    active: bool | None = None


# --- Lado operador -----------------------------------------------------------

@router.get("/dashboards")
def list_dashboards(db: Session = Depends(get_db), user: User = Depends(require("dashboard.view"))):
    return dashboard_service.list_dashboards(db, user)


@router.get("/dashboards/{key}")
def render_dashboard(key: str, db: Session = Depends(get_db), user: User = Depends(require("dashboard.view"))):
    """Renderiza una vista resumen resolviendo cada widget configurado."""
    payload = dashboard_service.render(db, key, user)
    if payload.get("dashboard") is None:
        raise HTTPException(404, f"Vista resumen no encontrada o inactiva: {key}")
    return payload


# --- Lado administrador / modo DEV ------------------------------------------

@router.get("/dev/widgets")
def widget_catalog(area: str | None = None, db: Session = Depends(get_db),
                   user: User = Depends(require("dashboard.configure"))):
    """Catálogo de widgets disponibles para colocar.

    Es el registro en código (``app/services/widgets.py``). Agregar un widget
    nuevo allí lo hace aparecer aquí sin migraciones ni cambios de interfaz.
    """
    return {"sizes": list(widget_registry.SIZES),
            "kinds": [widget_registry.KIND_METRIC, widget_registry.KIND_LIST,
                      widget_registry.KIND_BREAKDOWN, widget_registry.KIND_ALERT],
            "areas": {code: a.name for code, a in AREAS.items()},
            "widgets": widget_registry.catalog(area)}


@router.get("/dev/dashboards/{key}")
def dashboard_layout(key: str, db: Session = Depends(get_db),
                     user: User = Depends(require("dashboard.configure"))):
    """Configuración cruda de un dashboard, sin filtrar por permisos.

    El administrador necesita ver también lo oculto y lo restringido; si se
    filtrara como al operador, no podría volver a mostrar lo que ocultó.
    """
    layout = dashboard_service.layout_for_admin(db, key)
    if not layout:
        raise HTTPException(404, f"Vista resumen no encontrada: {key}")
    return layout


@router.put("/dev/dashboards/{key}")
def save_dashboard_layout(key: str, data: LayoutIn, db: Session = Depends(get_db),
                          user: User = Depends(require("dashboard.configure"))):
    """Guarda la composición completa de un dashboard.

    Se sustituye en bloque: la configuración es un documento ordenado y una
    validación fallida no debe dejar media composición aplicada.
    """
    dashboard = db.scalar(select(DashboardDefinition).where(DashboardDefinition.key == key))
    if not dashboard:
        raise HTTPException(404, f"Vista resumen no encontrada: {key}")
    before = [
        {"widget_key": p.widget_key, "visible": p.visible, "position": p.position, "size": p.size}
        for p in db.scalars(select(DashboardWidgetPlacement)
                            .where(DashboardWidgetPlacement.dashboard_id == dashboard.id)).all()
    ]
    known_roles = {r.name for r in db.scalars(select(Role)).all()}
    try:
        count = dashboard_service.replace_layout(
            db, dashboard, [p.model_dump() for p in data.placements], known_roles
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    audit(db, user_id=user.id, action="DASHBOARD_LAYOUT_SET", entity_type="DASHBOARD", entity_id=dashboard.id,
          before={"placements": before},
          after={"placements": [p.model_dump() for p in data.placements]})
    db.commit()
    return {"dashboard": key, "placements": count}


@router.post("/dev/dashboards")
def create_dashboard(data: DashboardIn, db: Session = Depends(get_db),
                     user: User = Depends(require("dashboard.configure"))):
    """Crea una vista resumen adicional, por ejemplo específica de un área."""
    key = data.key.strip().lower()
    if db.scalar(select(DashboardDefinition).where(DashboardDefinition.key == key)):
        raise HTTPException(409, f"Ya existe una vista resumen con la clave {key}")
    area_code = data.area_code.strip().upper()
    if area_code not in AREAS:
        raise HTTPException(422, f"Área desconocida: {area_code}")
    dashboard = DashboardDefinition(
        key=key, name=data.name.strip(), description=data.description, area_code=area_code,
        sort_order=data.sort_order, is_system=False,
    )
    db.add(dashboard)
    audit(db, user_id=user.id, action="DASHBOARD_CREATE", entity_type="DASHBOARD", entity_id=key,
          after=data.model_dump())
    db.commit()
    return {"key": dashboard.key, "id": dashboard.id}


@router.patch("/dev/dashboards/{key}")
def update_dashboard(key: str, data: DashboardPatchIn, db: Session = Depends(get_db),
                     user: User = Depends(require("dashboard.configure"))):
    dashboard = db.scalar(select(DashboardDefinition).where(DashboardDefinition.key == key))
    if not dashboard:
        raise HTTPException(404, f"Vista resumen no encontrada: {key}")
    if data.area_code is not None:
        area_code = data.area_code.strip().upper()
        if area_code not in AREAS:
            raise HTTPException(422, f"Área desconocida: {area_code}")
        dashboard.area_code = area_code
    if data.name is not None:
        dashboard.name = data.name.strip()
    if data.description is not None:
        dashboard.description = data.description
    if data.sort_order is not None:
        dashboard.sort_order = data.sort_order
    if data.active is not None:
        # Los dashboards semilla pueden desactivarse pero no borrarse: conservan
        # la configuración por si el administrador se arrepiente.
        dashboard.active = data.active
    audit(db, user_id=user.id, action="DASHBOARD_UPDATE", entity_type="DASHBOARD", entity_id=dashboard.id,
          after=data.model_dump(exclude_none=True))
    db.commit()
    return {"key": dashboard.key, "active": dashboard.active}


@router.delete("/dev/dashboards/{key}")
def delete_dashboard(key: str, db: Session = Depends(get_db),
                     user: User = Depends(require("dashboard.configure"))):
    """Elimina una vista resumen creada por un administrador.

    Las vistas semilla (``is_system``) no se borran: desactivarlas es
    reversible, borrarlas perdería la composición de referencia del producto.
    """
    dashboard = db.scalar(select(DashboardDefinition).where(DashboardDefinition.key == key))
    if not dashboard:
        raise HTTPException(404, f"Vista resumen no encontrada: {key}")
    if dashboard.is_system:
        raise HTTPException(409, "Una vista resumen del sistema no se elimina; desactívela con PATCH active=false")
    db.delete(dashboard)
    audit(db, user_id=user.id, action="DASHBOARD_DELETE", entity_type="DASHBOARD", entity_id=dashboard.id,
          before={"key": key})
    db.commit()
    return {"deleted": key}
