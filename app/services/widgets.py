"""Registro de widgets de la Vista Resumen.

Arquitectura
------------
El dashboard anterior era una función que devolvía siete contadores fijos.
Agregar una tarjeta obligaba a tocar el endpoint, el JSON de respuesta y la
plantilla. Este módulo separa dos cosas que antes estaban mezcladas:

* **catálogo de widgets disponibles** → código versionado, aquí;
* **qué se muestra, en qué orden, con qué tamaño y para quién** → configuración
  editable desde el modo DEV (tablas ``dashboard_definitions`` y
  ``dashboard_widget_placements``).

Cómo agregar un widget nuevo
----------------------------
Basta una función decorada con :func:`widget`. No hay que tocar el endpoint, ni
la interfaz, ni la base de datos::

    @widget(key="mi_metrica", title="Mi métrica", area="MATERIAL",
            kind=KIND_METRIC, permission="assets.view",
            description="Qué responde esta tarjeta")
    def _mi_metrica(db, ctx):
        return metric(db.scalar(select(func.count()).select_from(Asset)) or 0)

Al arrancar, el widget aparece en el catálogo del modo DEV y puede colocarse en
cualquier dashboard. La documentación extendida está en
``docs/30_DASHBOARD_CONFIGURABLE_Y_WIDGETS.md``.

Seguridad
---------
Cada widget declara el permiso que exige. El renderizado NUNCA entrega un
widget cuyo permiso no posee el usuario, aunque la configuración lo haya
colocado en su dashboard: la colocación puede restringir más (``role_names``),
nunca ampliar. Un fallo al resolver un widget se aísla y se reporta como error
de esa tarjeta, para que un widget roto no deje al operador sin vista resumen.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Asset, AssetType, AttendanceRecord, CaseRecord, CatalogItem, EmploymentEngagement, EvidenceRecord,
    InventoryCount, InventorySession, MaintenanceOrder, OperationalEvent, Person, PersonHRProfile,
    EppRequest, TrainingRecord, TransportAssignment, TransportIncident, User,
)

logger = logging.getLogger(__name__)

# Tipos de presentación que la interfaz sabe dibujar. Un widget nuevo debería
# reutilizar uno de éstos antes que introducir un tipo propio.
KIND_METRIC = "METRIC"        # un número grande con matiz y enlace
KIND_LIST = "LIST"            # lista corta de elementos accionables
KIND_BREAKDOWN = "BREAKDOWN"  # desglose etiqueta/valor
KIND_ALERT = "ALERT"          # lista de excepciones que piden atención

SIZES = ("SMALL", "MEDIUM", "LARGE", "FULL")

#: Matices visuales. ``bad`` y ``warn`` señalan algo que requiere atención; no
#: implican una sanción ni un veredicto automático del sistema.
TONE_NEUTRAL, TONE_OK, TONE_WARN, TONE_BAD = "neutral", "ok", "warn", "bad"


@dataclass(frozen=True)
class WidgetContext:
    """Contexto con el que se resuelve un widget para un usuario concreto."""

    user: User
    permissions: frozenset[str]
    area_codes: frozenset[str]
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WidgetDefinition:
    """Declaración de un widget disponible en el catálogo."""

    key: str
    title: str
    area: str
    kind: str
    permission: str
    description: str
    resolver: Callable[[Session, WidgetContext], dict]
    default_size: str = "SMALL"
    default_position: int = 100
    #: Preguntas del apartado 11 del encargo que ayuda a responder.
    answers: tuple[str, ...] = ()

    def as_catalog_entry(self) -> dict:
        return {
            "key": self.key, "title": self.title, "area": self.area, "kind": self.kind,
            "permission": self.permission, "description": self.description,
            "default_size": self.default_size, "default_position": self.default_position,
            "answers": list(self.answers),
        }


#: Catálogo global. Se llena por decorador al importar el módulo.
REGISTRY: dict[str, WidgetDefinition] = {}


def widget(*, key: str, title: str, area: str, kind: str, permission: str, description: str,
           default_size: str = "SMALL", default_position: int = 100, answers: tuple[str, ...] = ()):
    """Registra una función como widget del catálogo.

    Falla ruidosamente ante una clave duplicada o un tamaño inválido: es un
    error de programación que debe detectarse al importar, no al renderizar el
    dashboard de un operador en campo.
    """

    def decorator(fn: Callable[[Session, WidgetContext], dict]) -> Callable[[Session, WidgetContext], dict]:
        if key in REGISTRY:
            raise ValueError(f"Widget duplicado en el registro: {key}")
        if default_size not in SIZES:
            raise ValueError(f"Tamaño inválido para {key}: {default_size}")
        REGISTRY[key] = WidgetDefinition(
            key=key, title=title, area=area, kind=kind, permission=permission,
            description=description, resolver=fn, default_size=default_size,
            default_position=default_position, answers=answers,
        )
        return fn

    return decorator


# --- Constructores de payload ------------------------------------------------
# Existen para que todos los widgets devuelvan la misma forma y la interfaz no
# tenga que conocer cada uno por separado.

def metric(value: int, *, hint: str = "", tone: str = TONE_NEUTRAL, link: dict | None = None) -> dict:
    return {"value": value, "hint": hint, "tone": tone, "link": link}


def listing(items: list[dict], *, empty: str = "Sin registros", tone: str = TONE_NEUTRAL) -> dict:
    return {"items": items, "empty": empty, "tone": tone}


def breakdown(rows: list[dict], *, empty: str = "Sin datos") -> dict:
    return {"rows": rows, "empty": empty}


def _link(view: str, **params: Any) -> dict:
    """Destino de navegación de un widget.

    La interfaz resuelve ``view`` contra su tabla de vistas; los parámetros
    viajan opacos. Así el backend sugiere a dónde ir sin conocer rutas de UI.
    """
    return {"view": view, "params": {k: v for k, v in params.items() if v is not None}}


def _critical_status_codes(db: Session) -> list[str]:
    """Estados marcados como críticos en el catálogo ``ASSET_STATUS``.

    Se leen de base de datos y no de una lista en código: el encargo exige que
    los estados sean configurables y que un estado nuevo no obligue a editar
    condicionales.
    """
    return [
        item.code
        for item in db.scalars(select(CatalogItem).where(CatalogItem.catalog == "ASSET_STATUS", CatalogItem.active.is_(True))).all()
        if (item.metadata_json or {}).get("critical")
    ]


def _node_type_ids(db: Session) -> list[str]:
    """Identificadores de los tipos de activo con capacidad ``node_field``.

    Se resuelve por capacidad, nunca por el literal ``"NODE"``: una tecnología
    futura puede registrarse como otro tipo y seguir siendo un nodo de campo.
    """
    return [t.id for t in db.scalars(select(AssetType)).all() if "node_field" in (t.capabilities or [])]


def _count_assets_by_status(db: Session, status_codes: list[str], *, only_nodes: bool = False) -> int:
    if not status_codes:
        return 0
    stmt = select(func.count()).select_from(Asset).where(Asset.active.is_(True), Asset.status_code.in_(status_codes))
    if only_nodes:
        type_ids = _node_type_ids(db)
        if not type_ids:
            return 0
        stmt = stmt.where(Asset.asset_type_id.in_(type_ids))
    return db.scalar(stmt) or 0


def _person_name(db: Session, person_id: str | None) -> str:
    if not person_id:
        return "—"
    person = db.get(Person, person_id)
    return person.full_name if person else "—"


def _asset_label(db: Session, asset: Asset | None) -> str:
    """Etiqueta legible de un activo, priorizando lo que el operador reconoce."""
    if asset is None:
        return "—"
    return asset.internal_code or asset.serial_number or asset.id[:8]


# --- Widgets de RRHH ---------------------------------------------------------

@widget(key="hr_personal_activo", title="Personal activo", area="RRHH", kind=KIND_METRIC,
        permission="person.view", description="Personas con al menos una relación laboral vigente.",
        default_position=10, answers=("¿Qué está pasando?",))
def _hr_personal_activo(db: Session, ctx: WidgetContext) -> dict:
    total = db.scalar(select(func.count()).select_from(Person).where(Person.active.is_(True))) or 0
    return metric(total, hint="con relación laboral vigente", tone=TONE_OK, link=_link("people"))


@widget(key="hr_personal_descanso", title="Personal en descanso", area="RRHH", kind=KIND_METRIC,
        permission="person.view", description="Personas con asistencia de hoy marcada como descanso.",
        default_position=20, answers=("¿Qué está pasando?",))
def _hr_personal_descanso(db: Session, ctx: WidgetContext) -> dict:
    today = date.today()
    total = db.scalar(
        select(func.count()).select_from(AttendanceRecord)
        .where(AttendanceRecord.attendance_date == today, AttendanceRecord.status == "REST")
    ) or 0
    return metric(total, hint="según la asistencia de hoy", link=_link("attendance"))


@widget(key="hr_altas_recientes", title="Altas recientes", area="RRHH", kind=KIND_LIST,
        permission="person.view", description="Relaciones laborales iniciadas en los últimos 30 días.",
        default_size="MEDIUM", default_position=30, answers=("¿Qué cambió?",))
def _hr_altas_recientes(db: Session, ctx: WidgetContext) -> dict:
    since = date.today() - timedelta(days=30)
    rows = db.scalars(
        select(EmploymentEngagement).where(EmploymentEngagement.start_date >= since)
        .order_by(EmploymentEngagement.start_date.desc()).limit(8)
    ).all()
    return listing(
        [{"primary": _person_name(db, r.person_id), "secondary": r.position or r.employment_id,
          "meta": r.start_date.isoformat(), "link": _link("person", id=r.person_id)} for r in rows],
        empty="Sin altas en los últimos 30 días",
    )


@widget(key="hr_bajas_recientes", title="Bajas recientes", area="RRHH", kind=KIND_LIST,
        permission="person.view", description="Relaciones laborales cerradas en los últimos 30 días.",
        default_size="MEDIUM", default_position=40, answers=("¿Qué cambió?",))
def _hr_bajas_recientes(db: Session, ctx: WidgetContext) -> dict:
    since = date.today() - timedelta(days=30)
    rows = db.scalars(
        select(EmploymentEngagement).where(EmploymentEngagement.end_date.is_not(None), EmploymentEngagement.end_date >= since)
        .order_by(EmploymentEngagement.end_date.desc()).limit(8)
    ).all()
    # La baja cierra la contratación, no la identidad: el enlace sigue llevando
    # al expediente de la persona, que permanece consultable.
    return listing(
        [{"primary": _person_name(db, r.person_id), "secondary": r.position or r.employment_id,
          "meta": r.end_date.isoformat() if r.end_date else "—", "link": _link("person", id=r.person_id)} for r in rows],
        empty="Sin bajas en los últimos 30 días",
    )


@widget(key="hr_asistencia_hoy", title="Asistencia del día", area="RRHH", kind=KIND_BREAKDOWN,
        permission="person.view", description="Desglose de la asistencia capturada para la fecha de hoy.",
        default_size="MEDIUM", default_position=50, answers=("¿Qué está pasando?",))
def _hr_asistencia_hoy(db: Session, ctx: WidgetContext) -> dict:
    today = date.today()
    rows = db.execute(
        select(AttendanceRecord.status, func.count()).where(AttendanceRecord.attendance_date == today)
        .group_by(AttendanceRecord.status)
    ).all()
    names = {c.code: c.name for c in db.scalars(select(CatalogItem).where(CatalogItem.catalog == "ATTENDANCE_STATUS")).all()}
    tones = {"ABSENT": TONE_WARN, "MEDICAL": TONE_WARN, "PRESENT": TONE_OK}
    return breakdown(
        [{"label": names.get(code, code), "value": count, "tone": tones.get(code, TONE_NEUTRAL)} for code, count in rows],
        empty="Todavía no se captura asistencia de hoy",
    )


@widget(key="hr_epp_pendiente", title="Solicitudes EPP pendientes", area="RRHH", kind=KIND_METRIC,
        permission="epp.view", description="Solicitudes de EPP esperando resolución de RRHH.",
        default_position=60, answers=("¿Qué está pendiente?", "¿Qué debo atender yo?"))
def _hr_epp_pendiente(db: Session, ctx: WidgetContext) -> dict:
    total = db.scalar(select(func.count()).select_from(EppRequest).where(EppRequest.status == "PENDING")) or 0
    return metric(total, hint="esperan validación de RRHH", tone=TONE_WARN if total else TONE_OK, link=_link("epp"))


# --- Widgets de Seguridad / HSE ----------------------------------------------

@widget(key="hse_licencias_por_vencer", title="Licencias próximas a vencer", area="HSE", kind=KIND_LIST,
        permission="person.view", description="Licencias de conducir/operación que vencen en los próximos 45 días.",
        default_size="MEDIUM", default_position=10, answers=("¿Qué requiere atención?",))
def _hse_licencias_por_vencer(db: Session, ctx: WidgetContext) -> dict:
    horizon = date.today() + timedelta(days=int(ctx.options.get("dias", 45)))
    rows = db.scalars(
        select(PersonHRProfile).where(PersonHRProfile.license_expiry.is_not(None), PersonHRProfile.license_expiry <= horizon)
        .order_by(PersonHRProfile.license_expiry).limit(10)
    ).all()
    today = date.today()
    return listing(
        [{"primary": _person_name(db, r.person_id),
          "secondary": f"{r.license_type or 'Licencia'} {r.license_number or ''}".strip(),
          "meta": r.license_expiry.isoformat() if r.license_expiry else "—",
          "tone": TONE_BAD if r.license_expiry and r.license_expiry < today else TONE_WARN,
          "link": _link("person", id=r.person_id)} for r in rows],
        empty="Sin licencias por vencer en el horizonte configurado",
    )


@widget(key="hse_cursos_pendientes", title="Cursos pendientes", area="HSE", kind=KIND_METRIC,
        permission="training.view", description="Cursos en lista de espera o programados sin acreditar.",
        default_position=20, answers=("¿Qué está pendiente?",))
def _hse_cursos_pendientes(db: Session, ctx: WidgetContext) -> dict:
    total = db.scalar(
        select(func.count()).select_from(TrainingRecord).where(TrainingRecord.state.in_(["WAITLIST", "SCHEDULED"]))
    ) or 0
    return metric(total, hint="esperan confirmación de HSE", tone=TONE_WARN if total else TONE_OK, link=_link("training"))


@widget(key="hse_incidencias_abiertas", title="Incidencias abiertas", area="HSE", kind=KIND_METRIC,
        permission="cases.create", description="Casos registrados sin resolución del área competente.",
        default_position=30, answers=("¿Qué requiere atención?",))
def _hse_incidencias_abiertas(db: Session, ctx: WidgetContext) -> dict:
    total = db.scalar(select(func.count()).select_from(CaseRecord).where(CaseRecord.status == "OPEN")) or 0
    return metric(total, hint="hechos registrados, aún sin resolver", tone=TONE_WARN if total else TONE_OK, link=_link("cases"))


# --- Widgets de Transporte ---------------------------------------------------

@widget(key="transporte_unidades_disponibles", title="Unidades disponibles", area="TRANSPORTE", kind=KIND_METRIC,
        permission="transport.view", description="Unidades de transporte con disponibilidad declarada AVAILABLE.",
        default_position=10, answers=("¿Qué está pasando?",))
def _transporte_disponibles(db: Session, ctx: WidgetContext) -> dict:
    total = db.scalar(
        select(func.count(func.distinct(TransportAssignment.unit_asset_id)))
        .where(TransportAssignment.end_at.is_(None), TransportAssignment.availability == "AVAILABLE")
    ) or 0
    return metric(total, hint="listas para asignar", tone=TONE_OK, link=_link("transport"))


@widget(key="transporte_unidades_incidencia", title="Unidades con incidencia", area="TRANSPORTE", kind=KIND_ALERT,
        permission="transport.view", description="Incidencias de transporte abiertas, con su unidad y conductor.",
        default_size="MEDIUM", default_position=20, answers=("¿Qué requiere atención?",))
def _transporte_incidencias(db: Session, ctx: WidgetContext) -> dict:
    rows = db.scalars(
        select(TransportIncident).where(TransportIncident.status == "OPEN")
        .order_by(TransportIncident.occurred_at.desc()).limit(10)
    ).all()
    return listing(
        [{"primary": _asset_label(db, db.get(Asset, r.unit_asset_id)),
          "secondary": f"{r.incident_type} · {_person_name(db, r.driver_person_id)}",
          "meta": r.occurred_at.date().isoformat(),
          "tone": TONE_BAD if r.severity in ("HIGH", "CRITICAL") else TONE_WARN,
          "link": _link("transport-unit", id=r.unit_asset_id)} for r in rows],
        empty="Sin incidencias de transporte abiertas", tone=TONE_OK,
    )


@widget(key="transporte_checklist_fallido", title="Checklist con hallazgos", area="TRANSPORTE", kind=KIND_METRIC,
        permission="transport.view", description="Checklist de los últimos 7 días con resultado distinto de PASS.",
        default_position=30, answers=("¿Qué requiere atención?",))
def _transporte_checklist(db: Session, ctx: WidgetContext) -> dict:
    from app.db.models import TransportChecklist  # import local: evita ciclo de lectura del módulo

    since = datetime.now(timezone.utc) - timedelta(days=7)
    total = db.scalar(
        select(func.count()).select_from(TransportChecklist)
        .where(TransportChecklist.occurred_at >= since, TransportChecklist.result != "PASS")
    ) or 0
    return metric(total, hint="en los últimos 7 días", tone=TONE_WARN if total else TONE_OK, link=_link("transport"))


# --- Widgets de Operación / Tracking Nodes -----------------------------------

def _nodes_metric(db: Session, status_code: str, hint: str, tone: str) -> dict:
    return metric(_count_assets_by_status(db, [status_code], only_nodes=True), hint=hint, tone=tone,
                  link=_link("assets", status=status_code))


@widget(key="nodos_plantados", title="Nodos plantados", area="OPERACION", kind=KIND_METRIC,
        permission="nodes.view", description="Nodos cuyo estado actual derivado del historial es tendido/en campo.",
        default_position=10, answers=("¿Qué está pasando?",))
def _nodos_plantados(db: Session, ctx: WidgetContext) -> dict:
    return _nodes_metric(db, "DEPLOYED", "tendidos en campo", TONE_OK)


@widget(key="nodos_no_encontrados", title="Nodos no encontrados", area="OPERACION", kind=KIND_METRIC,
        permission="nodes.view", description="Nodos reportados como no encontrados en campo.",
        default_position=20, answers=("¿Qué requiere atención?",))
def _nodos_no_encontrados(db: Session, ctx: WidgetContext) -> dict:
    return _nodes_metric(db, "MISSING", "reportados sin localizar", TONE_BAD)


@widget(key="nodos_danados", title="Nodos dañados", area="OPERACION", kind=KIND_METRIC,
        permission="nodes.view", description="Nodos con estado actual dañado.",
        default_position=30, answers=("¿Qué requiere atención?",))
def _nodos_danados(db: Session, ctx: WidgetContext) -> dict:
    return _nodes_metric(db, "DAMAGED", "pendientes de taller o baja", TONE_WARN)


@widget(key="nodos_en_taller", title="Nodos en taller", area="OPERACION", kind=KIND_METRIC,
        permission="nodes.view", description="Nodos actualmente en mantenimiento.",
        default_position=40, answers=("¿Qué está pendiente?",))
def _nodos_en_taller(db: Session, ctx: WidgetContext) -> dict:
    return _nodes_metric(db, "MAINTENANCE", "en intervención técnica", TONE_WARN)


@widget(key="nodos_excepciones", title="Excepciones de nodos", area="OPERACION", kind=KIND_BREAKDOWN,
        permission="nodes.view", description="Desglose de nodos por cada estado marcado como crítico en el catálogo.",
        default_size="MEDIUM", default_position=50, answers=("¿Qué requiere atención?",))
def _nodos_excepciones(db: Session, ctx: WidgetContext) -> dict:
    codes = _critical_status_codes(db)
    names = {c.code: c.name for c in db.scalars(select(CatalogItem).where(CatalogItem.catalog == "ASSET_STATUS")).all()}
    rows = []
    for code in codes:
        count = _count_assets_by_status(db, [code], only_nodes=True)
        if count:
            rows.append({"label": names.get(code, code), "value": count, "tone": TONE_BAD})
    return breakdown(rows, empty="Sin excepciones críticas de nodos")


@widget(key="operacion_actividad_reciente", title="Cambios recientes", area="OPERACION", kind=KIND_LIST,
        permission="dashboard.view", description="Últimos eventos registrados en el Tracking Core.",
        default_size="LARGE", default_position=60, answers=("¿Qué cambió?",))
def _actividad_reciente(db: Session, ctx: WidgetContext) -> dict:
    rows = db.scalars(select(OperationalEvent).order_by(OperationalEvent.recorded_at.desc()).limit(12)).all()
    return listing(
        [{"primary": r.event_type, "secondary": f"{r.entity_type} · {r.entity_id[:8]}",
          # occurred_at ≠ recorded_at: se muestran los dos porque el desfase
          # entre campo y captura es información operativa, no ruido.
          "meta": f"ocurrió {r.occurred_at:%d/%m %H:%M} · registrado {r.recorded_at:%d/%m %H:%M}"} for r in rows],
        empty="Sin actividad registrada",
    )


# --- Widgets de Control de Material ------------------------------------------

@widget(key="material_activos_total", title="Activos registrados", area="MATERIAL", kind=KIND_METRIC,
        permission="assets.view", description="Total de activos vigentes en el Asset Core.",
        default_position=10, answers=("¿Qué está pasando?",))
def _material_total(db: Session, ctx: WidgetContext) -> dict:
    total = db.scalar(select(func.count()).select_from(Asset).where(Asset.active.is_(True))) or 0
    return metric(total, hint="en el Asset Core", link=_link("assets"))


@widget(key="material_faltantes", title="Material faltante", area="MATERIAL", kind=KIND_METRIC,
        permission="inventory.manage", description="Activos no localizados en inventarios abiertos. Un faltante NO es una pérdida definitiva.",
        default_position=20, answers=("¿Qué requiere atención?",))
def _material_faltantes(db: Session, ctx: WidgetContext) -> dict:
    open_sessions = select(InventorySession.id).where(InventorySession.status == "OPEN")
    total = db.scalar(
        select(func.count()).select_from(InventoryCount)
        .where(InventoryCount.found.is_(False), InventoryCount.session_id.in_(open_sessions))
    ) or 0
    return metric(total, hint="observados como no encontrados; requiere conciliación",
                  tone=TONE_WARN if total else TONE_OK, link=_link("inventory"))


@widget(key="material_criticos", title="Activos en excepción", area="MATERIAL", kind=KIND_METRIC,
        permission="assets.view", description="Activos en cualquier estado marcado como crítico en el catálogo.",
        default_position=30, answers=("¿Qué requiere atención?",))
def _material_criticos(db: Session, ctx: WidgetContext) -> dict:
    total = _count_assets_by_status(db, _critical_status_codes(db))
    return metric(total, hint="dañado, robado, extraviado, no encontrado…",
                  tone=TONE_BAD if total else TONE_OK, link=_link("assets"))


@widget(key="material_por_estado", title="Activos por estado", area="MATERIAL", kind=KIND_BREAKDOWN,
        permission="assets.view", description="Distribución del inventario vigente por estado actual.",
        default_size="MEDIUM", default_position=40, answers=("¿Qué está pasando?",))
def _material_por_estado(db: Session, ctx: WidgetContext) -> dict:
    rows = db.execute(
        select(Asset.status_code, func.count()).where(Asset.active.is_(True)).group_by(Asset.status_code)
    ).all()
    catalog = {c.code: c for c in db.scalars(select(CatalogItem).where(CatalogItem.catalog == "ASSET_STATUS")).all()}
    out = []
    for code, count in sorted(rows, key=lambda r: -r[1]):
        item = catalog.get(code)
        critical = bool((item.metadata_json or {}).get("critical")) if item else False
        out.append({"label": item.name if item else code, "value": count, "tone": TONE_BAD if critical else TONE_NEUTRAL})
    return breakdown(out, empty="Sin activos registrados")


@widget(key="material_inventarios_abiertos", title="Inventarios pendientes", area="MATERIAL", kind=KIND_LIST,
        permission="assets.view", description="Levantamientos de inventario que siguen abiertos.",
        default_size="MEDIUM", default_position=50, answers=("¿Qué está pendiente?",))
def _material_inventarios(db: Session, ctx: WidgetContext) -> dict:
    rows = db.scalars(
        select(InventorySession).where(InventorySession.status == "OPEN")
        .order_by(InventorySession.started_at.desc()).limit(8)
    ).all()
    return listing(
        [{"primary": r.name, "secondary": "Inventario abierto", "meta": r.started_at.date().isoformat(),
          "tone": TONE_WARN, "link": _link("inventory", id=r.id)} for r in rows],
        empty="Sin inventarios abiertos", tone=TONE_OK,
    )


@widget(key="material_evidencias_recientes", title="Evidencias recientes", area="MATERIAL", kind=KIND_LIST,
        permission="evidence.view", description="Últimas evidencias cargadas o indexadas desde NAS.",
        default_size="MEDIUM", default_position=60, answers=("¿Qué cambió?",))
def _material_evidencias(db: Session, ctx: WidgetContext) -> dict:
    rows = db.scalars(select(EvidenceRecord).order_by(EvidenceRecord.created_at.desc()).limit(8)).all()
    return listing(
        [{"primary": r.original_name, "secondary": f"{r.entity_type} · {r.source}",
          "meta": r.created_at.date().isoformat()} for r in rows],
        empty="Sin evidencias registradas",
    )


# --- Widgets de Taller / TX --------------------------------------------------

@widget(key="taller_ordenes_abiertas", title="Órdenes de taller abiertas", area="TALLER", kind=KIND_METRIC,
        permission="maintenance.view", description="Órdenes de mantenimiento que aún no se cierran.",
        default_position=10, answers=("¿Qué está pendiente?", "¿Qué debo atender yo?"))
def _taller_abiertas(db: Session, ctx: WidgetContext) -> dict:
    total = db.scalar(select(func.count()).select_from(MaintenanceOrder).where(MaintenanceOrder.status != "CLOSED")) or 0
    return metric(total, hint="en diagnóstico, prueba o reparación",
                  tone=TONE_WARN if total else TONE_OK, link=_link("maintenance"))


@widget(key="taller_espera_pieza", title="En espera de pieza", area="TALLER", kind=KIND_METRIC,
        permission="maintenance.view", description="Órdenes detenidas esperando refacción.",
        default_position=20, answers=("¿Qué está pendiente?",))
def _taller_espera(db: Session, ctx: WidgetContext) -> dict:
    total = db.scalar(
        select(func.count()).select_from(MaintenanceOrder).where(MaintenanceOrder.status == "WAITING_PART")
    ) or 0
    return metric(total, hint="detenidas por refacción", tone=TONE_WARN if total else TONE_OK, link=_link("maintenance"))


@widget(key="taller_recepcion", title="Recepción de taller", area="TALLER", kind=KIND_LIST,
        permission="maintenance.view", description="Últimos activos recibidos en taller y su estado de atención.",
        default_size="LARGE", default_position=30, answers=("¿Qué debo atender yo?",))
def _taller_recepcion(db: Session, ctx: WidgetContext) -> dict:
    rows = db.scalars(
        select(MaintenanceOrder).where(MaintenanceOrder.status != "CLOSED")
        .order_by(MaintenanceOrder.opened_at.desc()).limit(10)
    ).all()
    return listing(
        [{"primary": _asset_label(db, db.get(Asset, r.asset_id)),
          "secondary": r.symptom or r.fault_code or "Sin síntoma capturado",
          "meta": f"{r.status} · {r.opened_at:%d/%m}",
          "tone": TONE_WARN, "link": _link("maintenance", id=r.id)} for r in rows],
        empty="Sin órdenes abiertas en taller", tone=TONE_OK,
    )


# --- Widgets transversales ---------------------------------------------------

@widget(key="general_mis_pendientes", title="Qué debo atender", area="GENERAL", kind=KIND_ALERT,
        permission="dashboard.view", description="Pendientes filtrados por lo que el perfil del usuario puede resolver.",
        default_size="LARGE", default_position=5, answers=("¿Qué debo atender yo?",))
def _mis_pendientes(db: Session, ctx: WidgetContext) -> dict:
    """Pendientes accionables por *este* usuario.

    A diferencia de los contadores, aquí sólo entra lo que el usuario puede
    resolver con los permisos que tiene: mostrar una pendiente que no puede
    cerrar convierte la vista resumen en ruido.
    """
    items: list[dict] = []
    if "epp.validate_hr" in ctx.permissions:
        count = db.scalar(select(func.count()).select_from(EppRequest).where(EppRequest.status == "PENDING")) or 0
        if count:
            items.append({"primary": f"{count} solicitud(es) de EPP por validar", "secondary": "RRHH resuelve",
                          "tone": TONE_WARN, "link": _link("epp")})
    if "training.confirm_hse" in ctx.permissions:
        count = db.scalar(select(func.count()).select_from(TrainingRecord).where(TrainingRecord.state.in_(["WAITLIST", "SCHEDULED"]))) or 0
        if count:
            items.append({"primary": f"{count} curso(s) por acreditar", "secondary": "Seguridad/HSE confirma",
                          "tone": TONE_WARN, "link": _link("training")})
    if "cases.resolve" in ctx.permissions:
        count = db.scalar(select(func.count()).select_from(CaseRecord).where(CaseRecord.status == "OPEN")) or 0
        if count:
            items.append({"primary": f"{count} caso(s) abierto(s)", "secondary": "El área competente resuelve",
                          "tone": TONE_WARN, "link": _link("cases")})
    if "maintenance.manage" in ctx.permissions:
        count = db.scalar(select(func.count()).select_from(MaintenanceOrder).where(MaintenanceOrder.status != "CLOSED")) or 0
        if count:
            items.append({"primary": f"{count} orden(es) de taller abiertas", "secondary": "Taller/TX diagnostica",
                          "tone": TONE_WARN, "link": _link("maintenance")})
    if "inventory.closeout" in ctx.permissions:
        count = db.scalar(select(func.count()).select_from(InventorySession).where(InventorySession.status == "OPEN")) or 0
        if count:
            items.append({"primary": f"{count} inventario(s) por conciliar", "secondary": "Control de Material cierra",
                          "tone": TONE_WARN, "link": _link("inventory")})
    if "transport.manage" in ctx.permissions:
        count = db.scalar(select(func.count()).select_from(TransportIncident).where(TransportIncident.status == "OPEN")) or 0
        if count:
            items.append({"primary": f"{count} incidencia(s) de transporte", "secondary": "Transporte resuelve",
                          "tone": TONE_WARN, "link": _link("transport")})
    return listing(items, empty="Nada pendiente para tu perfil", tone=TONE_OK)


def catalog(area: str | None = None) -> list[dict]:
    """Catálogo de widgets disponibles, opcionalmente filtrado por área."""
    entries = [w.as_catalog_entry() for w in REGISTRY.values() if area is None or w.area == area]
    return sorted(entries, key=lambda e: (e["area"], e["default_position"], e["key"]))


def resolve(db: Session, definition: WidgetDefinition, ctx: WidgetContext) -> dict:
    """Ejecuta el resolver de un widget aislando sus fallos.

    Un widget que lance una excepción no debe dejar al operador sin vista
    resumen: se devuelve la tarjeta en estado de error y el resto se renderiza
    con normalidad. El detalle técnico va al log del servicio, no a la interfaz.
    """
    try:
        return {"ok": True, "data": definition.resolver(db, ctx)}
    except Exception:  # noqa: BLE001 - aislamiento deliberado por widget
        logger.exception("Fallo al resolver el widget %s", definition.key)
        return {"ok": False, "data": None, "error": "No se pudo calcular este indicador"}
