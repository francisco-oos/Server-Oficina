"""Vistas resumen configurables: definición, configuración DEV y renderizado.

Separación de responsabilidades
-------------------------------
``app/services/widgets.py``   qué widgets EXISTEN (catálogo en código)
``app/services/dashboards.py`` qué widgets se MUESTRAN (configuración en BD)

Un administrador en modo DEV decide mostrar, ocultar, ordenar, redimensionar,
retitular y restringir por perfil, sin que ningún cambio de interfaz requiera
tocar código. Las tarjetas dejaron de estar hardcodeadas.

Regla de siembra
----------------
La siembra sólo coloca widgets la **primera vez** que se crea un dashboard. Si
una release posterior agrega widgets nuevos, éstos aparecen en el catálogo DEV
pero NO se auto-insertan en dashboards existentes: reaparecer solas sería
sobrescribir una decisión explícita del administrador. La configuración es un
dato del operador, no una semilla que el arranque pueda pisar.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.areas import AREAS, AREA_GENERAL
from app.core.security import permission_codes
from app.db.models import DashboardDefinition, DashboardWidgetPlacement, RoleArea, User
from app.services import widgets as widget_registry

#: Clave del dashboard transversal que ve cualquier perfil.
GENERAL_KEY = "general"

#: Composición inicial del dashboard general. Responde a las preguntas del
#: apartado 11 del encargo (qué pasa / qué requiere atención / qué cambió /
#: qué está pendiente / qué debo atender yo) y no es una lista de contadores.
GENERAL_SEED: tuple[tuple[str, int, str], ...] = (
    ("general_mis_pendientes", 10, "FULL"),
    ("hr_personal_activo", 20, "SMALL"),
    ("material_activos_total", 30, "SMALL"),
    ("nodos_plantados", 40, "SMALL"),
    ("material_criticos", 50, "SMALL"),
    ("taller_ordenes_abiertas", 60, "SMALL"),
    ("transporte_unidades_disponibles", 70, "SMALL"),
    ("nodos_excepciones", 80, "MEDIUM"),
    ("material_por_estado", 90, "MEDIUM"),
    ("operacion_actividad_reciente", 100, "LARGE"),
)


def ensure_dashboards(db: Session) -> None:
    """Crea los dashboards semilla y su composición inicial (idempotente).

    Se invoca desde el ``lifespan`` de la aplicación, junto al resto del
    arranque. Crear un dashboard por área permite que un usuario de RRHH o de
    Transporte entre directamente a su vista sin pasar por la general.
    """
    _ensure_dashboard(
        db, key=GENERAL_KEY, name="Vista resumen general", area_code=AREA_GENERAL, sort_order=0,
        description="Panorama transversal: pendientes propios, estado operativo y cambios recientes.",
        seed=GENERAL_SEED,
    )
    for area in sorted(AREAS.values(), key=lambda a: a.sort_order):
        if area.code == AREA_GENERAL:
            continue
        area_widgets = [w for w in widget_registry.REGISTRY.values() if w.area == area.code]
        seed = tuple(
            (w.key, w.default_position, w.default_size)
            for w in sorted(area_widgets, key=lambda w: (w.default_position, w.key))
        )
        _ensure_dashboard(
            db, key=area.code.lower(), name=f"Vista resumen · {area.name}", area_code=area.code,
            sort_order=area.sort_order, description=area.description, seed=seed,
        )
    db.commit()


def _ensure_dashboard(db: Session, *, key: str, name: str, area_code: str, sort_order: int,
                      description: str, seed: tuple[tuple[str, int, str], ...]) -> DashboardDefinition:
    dashboard = db.scalar(select(DashboardDefinition).where(DashboardDefinition.key == key))
    if dashboard is None:
        dashboard = DashboardDefinition(
            key=key, name=name, description=description, area_code=area_code,
            sort_order=sort_order, is_system=True,
        )
        db.add(dashboard)
        db.flush()
    already_configured = db.scalar(
        select(DashboardWidgetPlacement.id).where(DashboardWidgetPlacement.dashboard_id == dashboard.id).limit(1)
    )
    if already_configured:
        # Ya tiene configuración del administrador: no se toca.
        return dashboard
    for widget_key, position, size in seed:
        if widget_key not in widget_registry.REGISTRY:
            continue
        db.add(DashboardWidgetPlacement(
            dashboard_id=dashboard.id, widget_key=widget_key, position=position, size=size, visible=True,
        ))
    return dashboard


def user_area_codes(db: Session, user: User) -> set[str]:
    """Áreas del usuario, derivadas de sus perfiles.

    Un perfil sin área declarada aporta ``GENERAL``. El área describe y
    prioriza; nunca autoriza por sí sola.
    """
    from app.core.areas import DEFAULT_ROLE_AREAS

    codes: set[str] = set()
    for role in user.roles:
        link = db.get(RoleArea, role.id)
        if link and link.area_code in AREAS:
            codes.add(link.area_code)
        else:
            codes.add(DEFAULT_ROLE_AREAS.get(role.name, AREA_GENERAL))
    return codes or {AREA_GENERAL}


def _context(db: Session, user: User, options: dict | None = None) -> widget_registry.WidgetContext:
    return widget_registry.WidgetContext(
        user=user,
        permissions=frozenset(permission_codes(user)),
        area_codes=frozenset(user_area_codes(db, user)),
        options=options or {},
    )


def list_dashboards(db: Session, user: User) -> list[dict]:
    """Dashboards activos, marcando cuáles corresponden al área del usuario."""
    areas = user_area_codes(db, user)
    rows = db.scalars(
        select(DashboardDefinition).where(DashboardDefinition.active.is_(True))
        .order_by(DashboardDefinition.sort_order, DashboardDefinition.name)
    ).all()
    return [
        {"key": d.key, "name": d.name, "description": d.description, "area": d.area_code,
         "is_system": d.is_system, "own_area": d.area_code in areas or d.area_code == AREA_GENERAL}
        for d in rows
    ]


def effective_placements(db: Session, dashboard: DashboardDefinition, user: User) -> list[tuple[DashboardWidgetPlacement, widget_registry.WidgetDefinition]]:
    """Colocaciones que este usuario puede ver, ya filtradas y ordenadas.

    Se descartan, en este orden:

    1. colocaciones ocultas por el administrador;
    2. colocaciones que apuntan a un ``widget_key`` que ya no existe en el
       catálogo (release que retiró el widget) — se ignoran en lugar de romper;
    3. widgets cuyo permiso el usuario no posee;
    4. widgets restringidos a perfiles a los que el usuario no pertenece.

    El punto 3 es la garantía de seguridad: la configuración puede restringir
    más, jamás otorgar visibilidad sobre datos que el permiso no concede.
    """
    permissions = permission_codes(user)
    role_names = {r.name for r in user.roles}
    rows = db.scalars(
        select(DashboardWidgetPlacement).where(DashboardWidgetPlacement.dashboard_id == dashboard.id)
        .order_by(DashboardWidgetPlacement.position, DashboardWidgetPlacement.widget_key)
    ).all()
    result = []
    for placement in rows:
        if not placement.visible:
            continue
        definition = widget_registry.REGISTRY.get(placement.widget_key)
        if definition is None:
            continue
        if definition.permission not in permissions:
            continue
        restricted = placement.role_names or []
        if restricted and not (role_names & set(restricted)):
            continue
        result.append((placement, definition))
    return result


def render(db: Session, dashboard_key: str, user: User) -> dict:
    """Renderiza una vista resumen completa para el usuario dado."""
    dashboard = db.scalar(select(DashboardDefinition).where(DashboardDefinition.key == dashboard_key))
    if dashboard is None or not dashboard.active:
        return {"dashboard": None, "widgets": []}
    ctx_cache: dict[str, widget_registry.WidgetContext] = {}
    cards = []
    for placement, definition in effective_placements(db, dashboard, user):
        options = placement.options or {}
        cache_key = repr(sorted(options.items()))
        if cache_key not in ctx_cache:
            ctx_cache[cache_key] = _context(db, user, options)
        resolved = widget_registry.resolve(db, definition, ctx_cache[cache_key])
        cards.append({
            "key": definition.key,
            "title": placement.title_override or definition.title,
            "area": definition.area,
            "kind": definition.kind,
            "size": placement.size,
            "position": placement.position,
            "description": definition.description,
            **resolved,
        })
    return {
        "dashboard": {"key": dashboard.key, "name": dashboard.name, "area": dashboard.area_code,
                      "description": dashboard.description},
        "widgets": cards,
    }


def layout_for_admin(db: Session, dashboard_key: str) -> dict:
    """Configuración cruda de un dashboard para el modo DEV.

    A diferencia de :func:`render`, aquí NO se filtra por permisos: el
    administrador necesita ver también lo que ha ocultado o restringido. Se
    marca cada colocación huérfana para que pueda limpiarla.
    """
    dashboard = db.scalar(select(DashboardDefinition).where(DashboardDefinition.key == dashboard_key))
    if dashboard is None:
        return {}
    rows = db.scalars(
        select(DashboardWidgetPlacement).where(DashboardWidgetPlacement.dashboard_id == dashboard.id)
        .order_by(DashboardWidgetPlacement.position, DashboardWidgetPlacement.widget_key)
    ).all()
    return {
        "dashboard": {"key": dashboard.key, "name": dashboard.name, "area": dashboard.area_code,
                      "description": dashboard.description, "active": dashboard.active,
                      "is_system": dashboard.is_system},
        "placements": [
            {"widget_key": p.widget_key, "visible": p.visible, "position": p.position, "size": p.size,
             "title_override": p.title_override, "role_names": p.role_names or [], "options": p.options or {},
             "orphan": p.widget_key not in widget_registry.REGISTRY,
             "title": widget_registry.REGISTRY[p.widget_key].title if p.widget_key in widget_registry.REGISTRY else p.widget_key,
             "area": widget_registry.REGISTRY[p.widget_key].area if p.widget_key in widget_registry.REGISTRY else None,
             "kind": widget_registry.REGISTRY[p.widget_key].kind if p.widget_key in widget_registry.REGISTRY else None,
             "permission": widget_registry.REGISTRY[p.widget_key].permission if p.widget_key in widget_registry.REGISTRY else None}
            for p in rows
        ],
    }


def replace_layout(db: Session, dashboard: DashboardDefinition, items: list[dict], known_roles: set[str]) -> int:
    """Sustituye por completo la composición de un dashboard.

    Se reemplaza en bloque —y no se parchea colocación por colocación— porque
    la configuración es un documento ordenado: reordenar, ocultar y quitar en
    una sola operación evita estados intermedios incoherentes si la petición
    falla a la mitad.

    Valida claves de widget, tamaños y nombres de perfil; una entrada inválida
    aborta el guardado completo en lugar de dejar media configuración aplicada.
    """
    normalized: list[DashboardWidgetPlacement] = []
    seen: set[str] = set()
    for index, raw in enumerate(items):
        key = str(raw.get("widget_key", "")).strip()
        if key not in widget_registry.REGISTRY:
            raise ValueError(f"Widget desconocido: {key or '(vacío)'}")
        if key in seen:
            raise ValueError(f"Widget repetido en el dashboard: {key}")
        seen.add(key)
        size = str(raw.get("size") or widget_registry.REGISTRY[key].default_size).upper()
        if size not in widget_registry.SIZES:
            raise ValueError(f"Tamaño inválido para {key}: {size}")
        roles = [str(r) for r in (raw.get("role_names") or [])]
        unknown = [r for r in roles if r not in known_roles]
        if unknown:
            raise ValueError(f"Perfil inexistente en la restricción de {key}: {', '.join(unknown)}")
        title = (raw.get("title_override") or "").strip() or None
        position = raw.get("position")
        normalized.append(DashboardWidgetPlacement(
            dashboard_id=dashboard.id, widget_key=key,
            visible=bool(raw.get("visible", True)),
            position=int(position) if position is not None else (index + 1) * 10,
            size=size, title_override=title, role_names=roles,
            options=raw.get("options") or {},
        ))
    for existing in db.scalars(select(DashboardWidgetPlacement).where(DashboardWidgetPlacement.dashboard_id == dashboard.id)).all():
        db.delete(existing)
    db.flush()
    for placement in normalized:
        db.add(placement)
    return len(normalized)
