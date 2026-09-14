"""API del dominio de Transporte.

Transporte gestiona su propio dominio y no se presenta como otro inventario:
unidad, conductor, asignaciones, teléfono, radio, proyecto, grupo,
disponibilidad, checklist, incidencias, mantenimiento e historial.

Reutilización sin duplicación
-----------------------------
La unidad ES un activo del Asset Core (``assets`` con tipo de capacidad
``transport``). El radio y el teléfono asociados también son activos ya
registrados. Este módulo declara la *relación temporal* entre ellos y la
persona; no crea un registro paralelo de vehículos, radios ni teléfonos. Así el
vínculo persona ↔ unidad ↔ conductor ↔ grupo ↔ ubicación se declara una vez y
se consulta desde RRHH, Operación o Material sin duplicar datos.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.db.base import get_db
from app.db.models import (
    Asset, AssetType, Location, MaintenanceOrder, Person, Project, TransportAssignment,
    TransportChecklist, TransportIncident, User, WorkGroup,
)
from app.services.audit import audit
from app.services.events import record_event
from app.services.lookup import asset_label, transport_dossier

router = APIRouter(prefix="/api/transport", tags=["transporte"])

#: Disponibilidades admitidas para una unidad.
AVAILABILITY = ("AVAILABLE", "ASSIGNED", "WORKSHOP", "DOWN")
#: Resultados admitidos de un checklist.
CHECKLIST_RESULTS = ("PASS", "PASS_WITH_FINDINGS", "FAIL")


class AssignmentIn(BaseModel):
    driver_person_id: str | None = None
    project_id: str | None = None
    group_id: str | None = None
    location_id: str | None = None
    radio_asset_id: str | None = None
    phone_asset_id: str | None = None
    availability: str = "ASSIGNED"
    occurred_at: datetime | None = None
    note: str | None = None


class ChecklistItemIn(BaseModel):
    code: str
    label: str
    ok: bool = True
    note: str | None = None


class ChecklistIn(BaseModel):
    driver_person_id: str | None = None
    result: str = "PASS"
    odometer_km: int | None = Field(default=None, ge=0)
    fuel_level: str | None = None
    items: list[ChecklistItemIn] = Field(default_factory=list)
    occurred_at: datetime | None = None
    note: str | None = None


class IncidentIn(BaseModel):
    incident_type: str = Field(min_length=2, max_length=80)
    severity: str = "NORMAL"
    summary: str = Field(min_length=3)
    driver_person_id: str | None = None
    location_id: str | None = None
    occurred_at: datetime | None = None


class IncidentResolveIn(BaseModel):
    resolution: str = Field(min_length=3)
    maintenance_order_id: str | None = None


def _transport_unit(db: Session, asset_id: str) -> Asset:
    """Obtiene un activo y verifica que sea realmente una unidad de transporte.

    La comprobación es por **capacidad declarada** del tipo (``transport``), no
    por el código del tipo: registrar mañana ``PICKUP`` o ``CAMION`` con esa
    capacidad debe funcionar sin tocar este archivo.
    """
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Unidad no encontrada")
    atype = db.get(AssetType, asset.asset_type_id)
    if not atype or "transport" not in (atype.capabilities or []):
        raise HTTPException(422, "El activo no declara la capacidad 'transport'; no es una unidad de transporte")
    return asset


def _check_person(db: Session, person_id: str | None, label: str) -> None:
    if person_id and not db.get(Person, person_id):
        raise HTTPException(404, f"{label} no encontrado")


def _check_asset(db: Session, asset_id: str | None, label: str) -> None:
    if asset_id and not db.get(Asset, asset_id):
        raise HTTPException(404, f"{label} no encontrado")


@router.get("/units")
def list_units(q: str = "", availability: str | None = None, project_id: str | None = None,
               db: Session = Depends(get_db), user: User = Depends(require("transport.view"))):
    """Listado de unidades con su asignación vigente resuelta.

    Devuelve el conductor, grupo, radio y teléfono actuales junto a la unidad
    para que la pantalla de Transporte sea utilizable sin abrir cada ficha.
    """
    type_ids = [t.id for t in db.scalars(select(AssetType)).all() if "transport" in (t.capabilities or [])]
    if not type_ids:
        return []
    stmt = select(Asset).where(Asset.active.is_(True), Asset.asset_type_id.in_(type_ids))
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Asset.internal_code.ilike(like), Asset.serial_number.ilike(like)))
    if project_id:
        stmt = stmt.where(Asset.current_project_id == project_id)
    units = db.scalars(stmt.order_by(Asset.internal_code).limit(200)).all()

    rows = []
    for unit in units:
        assignment = db.scalar(
            select(TransportAssignment).where(
                TransportAssignment.unit_asset_id == unit.id, TransportAssignment.end_at.is_(None)
            ).order_by(TransportAssignment.start_at.desc())
        )
        current_availability = assignment.availability if assignment else "AVAILABLE"
        if availability and current_availability != availability:
            continue
        open_incidents = db.scalar(
            select(func.count()).select_from(TransportIncident)
            .where(TransportIncident.unit_asset_id == unit.id, TransportIncident.status == "OPEN")
        ) or 0
        last_checklist = db.scalar(
            select(TransportChecklist).where(TransportChecklist.unit_asset_id == unit.id)
            .order_by(TransportChecklist.occurred_at.desc())
        )
        driver = db.get(Person, assignment.driver_person_id) if assignment and assignment.driver_person_id else None
        rows.append({
            "id": unit.id, "label": asset_label(db, unit), "status_code": unit.status_code,
            "availability": current_availability,
            "driver": driver.full_name if driver else None,
            "driver_person_id": driver.id if driver else None,
            "group": (db.get(WorkGroup, assignment.group_id).name if assignment and assignment.group_id and db.get(WorkGroup, assignment.group_id) else None),
            "project": (db.get(Project, unit.current_project_id).name if unit.current_project_id and db.get(Project, unit.current_project_id) else None),
            "location": (db.get(Location, unit.current_location_id).name if unit.current_location_id and db.get(Location, unit.current_location_id) else None),
            "radio": asset_label(db, db.get(Asset, assignment.radio_asset_id)) if assignment and assignment.radio_asset_id else None,
            "phone": asset_label(db, db.get(Asset, assignment.phone_asset_id)) if assignment and assignment.phone_asset_id else None,
            "open_incidents": open_incidents,
            "last_checklist": None if not last_checklist else {
                "result": last_checklist.result, "occurred_at": last_checklist.occurred_at,
            },
        })
    return rows


@router.get("/units/{asset_id}")
def unit_dossier(asset_id: str, db: Session = Depends(get_db), user: User = Depends(require("transport.view"))):
    """Ficha completa de una unidad de transporte."""
    _transport_unit(db, asset_id)
    dossier = transport_dossier(db, asset_id)
    if dossier is None:
        raise HTTPException(404, "Unidad no encontrada")
    return dossier


@router.post("/units/{asset_id}/assignments")
def assign_unit(asset_id: str, data: AssignmentIn, db: Session = Depends(get_db),
                user: User = Depends(require("transport.manage"))):
    """Declara una nueva asignación de la unidad, cerrando la anterior.

    No se sobrescribe la asignación previa: se le pone ``end_at`` y se abre una
    nueva. Quién conducía una unidad el día de una incidencia debe seguir siendo
    consultable después de reasignarla (estado actual ≠ historial).
    """
    unit = _transport_unit(db, asset_id)
    if data.availability not in AVAILABILITY:
        raise HTTPException(422, f"Disponibilidad inválida: {data.availability}. Válidas: {', '.join(AVAILABILITY)}")
    _check_person(db, data.driver_person_id, "Conductor")
    _check_asset(db, data.radio_asset_id, "Radio")
    _check_asset(db, data.phone_asset_id, "Teléfono")
    if data.project_id and not db.get(Project, data.project_id):
        raise HTTPException(404, "Proyecto no encontrado")
    if data.group_id and not db.get(WorkGroup, data.group_id):
        raise HTTPException(404, "Grupo no encontrado")
    if data.location_id and not db.get(Location, data.location_id):
        raise HTTPException(404, "Ubicación no encontrada")

    occurred_at = data.occurred_at or datetime.now(timezone.utc)
    for previous in db.scalars(
        select(TransportAssignment).where(
            TransportAssignment.unit_asset_id == asset_id, TransportAssignment.end_at.is_(None)
        )
    ).all():
        previous.end_at = occurred_at

    assignment = TransportAssignment(
        unit_asset_id=asset_id, driver_person_id=data.driver_person_id, project_id=data.project_id,
        group_id=data.group_id, location_id=data.location_id, radio_asset_id=data.radio_asset_id,
        phone_asset_id=data.phone_asset_id, availability=data.availability, start_at=occurred_at,
        actor_user_id=user.id, note=data.note,
    )
    db.add(assignment)
    db.flush()

    # La unidad es un activo: su proyecto/grupo/ubicación vigentes se
    # actualizan, pero su identidad y su historial de movimientos no se tocan.
    if data.project_id is not None:
        unit.current_project_id = data.project_id
    if data.group_id is not None:
        unit.current_group_id = data.group_id
    if data.location_id is not None:
        unit.current_location_id = data.location_id

    record_event(db, entity_type="ASSET", entity_id=asset_id, event_type="TRANSPORT_ASSIGNED",
                 occurred_at=occurred_at, project_id=data.project_id, source_type="UI", actor_user_id=user.id,
                 payload={"driver_person_id": data.driver_person_id, "availability": data.availability,
                          "group_id": data.group_id, "radio_asset_id": data.radio_asset_id,
                          "phone_asset_id": data.phone_asset_id})
    audit(db, user_id=user.id, action="TRANSPORT_ASSIGN", entity_type="ASSET", entity_id=asset_id,
          after=data.model_dump(mode="json"))
    db.commit()
    return {"id": assignment.id, "unit_asset_id": asset_id, "availability": assignment.availability}


@router.post("/units/{asset_id}/checklists")
def add_checklist(asset_id: str, data: ChecklistIn, db: Session = Depends(get_db),
                  user: User = Depends(require("transport.manage"))):
    """Registra un checklist de la unidad.

    Un resultado ``FAIL`` NO inmoviliza la unidad automáticamente: se registra
    el hecho y Transporte decide si cambia la disponibilidad. Es la misma regla
    que evidencia ≠ sanción aplicada al dominio de transporte.
    """
    _transport_unit(db, asset_id)
    if data.result not in CHECKLIST_RESULTS:
        raise HTTPException(422, f"Resultado inválido: {data.result}. Válidos: {', '.join(CHECKLIST_RESULTS)}")
    _check_person(db, data.driver_person_id, "Conductor")
    occurred_at = data.occurred_at or datetime.now(timezone.utc)
    checklist = TransportChecklist(
        unit_asset_id=asset_id, driver_person_id=data.driver_person_id, result=data.result,
        odometer_km=data.odometer_km, fuel_level=data.fuel_level,
        items_json=[item.model_dump() for item in data.items],
        occurred_at=occurred_at, actor_user_id=user.id, note=data.note,
    )
    db.add(checklist)
    db.flush()
    record_event(db, entity_type="ASSET", entity_id=asset_id, event_type="TRANSPORT_CHECKLIST",
                 occurred_at=occurred_at, source_type="UI", actor_user_id=user.id,
                 payload={"result": data.result, "odometer_km": data.odometer_km,
                          "findings": [i.code for i in data.items if not i.ok]})
    db.commit()
    return {"id": checklist.id, "result": checklist.result}


@router.get("/checklists")
def list_checklists(unit_asset_id: str | None = None, result: str | None = None, limit: int = 50,
                    db: Session = Depends(get_db), user: User = Depends(require("transport.view"))):
    stmt = select(TransportChecklist)
    if unit_asset_id:
        stmt = stmt.where(TransportChecklist.unit_asset_id == unit_asset_id)
    if result:
        stmt = stmt.where(TransportChecklist.result == result)
    rows = db.scalars(stmt.order_by(TransportChecklist.occurred_at.desc()).limit(min(limit, 200))).all()
    return [
        {"id": c.id, "unit_asset_id": c.unit_asset_id, "unit": asset_label(db, db.get(Asset, c.unit_asset_id)),
         "result": c.result, "odometer_km": c.odometer_km, "fuel_level": c.fuel_level,
         "driver": (db.get(Person, c.driver_person_id).full_name if c.driver_person_id and db.get(Person, c.driver_person_id) else None),
         "occurred_at": c.occurred_at, "recorded_at": c.recorded_at,
         "findings": [i for i in (c.items_json or []) if not i.get("ok", True)], "note": c.note}
        for c in rows
    ]


@router.post("/units/{asset_id}/incidents")
def report_incident(asset_id: str, data: IncidentIn, db: Session = Depends(get_db),
                    user: User = Depends(require("cases.create"))):
    """Reporta una incidencia de una unidad.

    Reportar exige ``cases.create`` y no ``transport.manage`` a propósito:
    cualquier área que presencie el hecho puede *proponerlo*. Sólo Transporte,
    que es la autoridad del dominio, puede *resolverlo*.
    """
    _transport_unit(db, asset_id)
    _check_person(db, data.driver_person_id, "Conductor")
    if data.location_id and not db.get(Location, data.location_id):
        raise HTTPException(404, "Ubicación no encontrada")
    occurred_at = data.occurred_at or datetime.now(timezone.utc)
    incident = TransportIncident(
        unit_asset_id=asset_id, driver_person_id=data.driver_person_id, incident_type=data.incident_type.strip(),
        severity=data.severity, summary=data.summary.strip(), occurred_at=occurred_at,
        location_id=data.location_id, reported_by=user.id,
    )
    db.add(incident)
    db.flush()
    record_event(db, entity_type="ASSET", entity_id=asset_id, event_type="TRANSPORT_INCIDENT",
                 occurred_at=occurred_at, source_type="UI", actor_user_id=user.id,
                 payload={"incident_type": incident.incident_type, "severity": incident.severity})
    audit(db, user_id=user.id, action="TRANSPORT_INCIDENT_REPORT", entity_type="ASSET", entity_id=asset_id,
          after=data.model_dump(mode="json"))
    db.commit()
    return {"id": incident.id, "status": incident.status}


@router.get("/incidents")
def list_incidents(status: str | None = None, unit_asset_id: str | None = None, limit: int = 50,
                   db: Session = Depends(get_db), user: User = Depends(require("transport.view"))):
    stmt = select(TransportIncident)
    if status:
        stmt = stmt.where(TransportIncident.status == status)
    if unit_asset_id:
        stmt = stmt.where(TransportIncident.unit_asset_id == unit_asset_id)
    rows = db.scalars(stmt.order_by(TransportIncident.occurred_at.desc()).limit(min(limit, 200))).all()
    return [
        {"id": i.id, "unit_asset_id": i.unit_asset_id, "unit": asset_label(db, db.get(Asset, i.unit_asset_id)),
         "incident_type": i.incident_type, "severity": i.severity, "summary": i.summary, "status": i.status,
         "driver": (db.get(Person, i.driver_person_id).full_name if i.driver_person_id and db.get(Person, i.driver_person_id) else None),
         "occurred_at": i.occurred_at, "recorded_at": i.recorded_at, "resolution": i.resolution,
         "maintenance_order_id": i.maintenance_order_id}
        for i in rows
    ]


@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: str, data: IncidentResolveIn, db: Session = Depends(get_db),
                     user: User = Depends(require("transport.manage"))):
    """Resuelve una incidencia como autoridad del dominio de Transporte.

    Puede enlazarse a una orden de taller existente. Enlazar NO convierte la
    incidencia en la orden: son dos hechos distintos con historias separadas.
    """
    incident = db.get(TransportIncident, incident_id)
    if not incident:
        raise HTTPException(404, "Incidencia no encontrada")
    if incident.status != "OPEN":
        raise HTTPException(409, "La incidencia ya está resuelta")
    if data.maintenance_order_id:
        order = db.get(MaintenanceOrder, data.maintenance_order_id)
        if not order:
            raise HTTPException(404, "Orden de taller no encontrada")
        if order.asset_id != incident.unit_asset_id:
            raise HTTPException(422, "La orden de taller corresponde a otro activo")
        incident.maintenance_order_id = order.id
    incident.status = "RESOLVED"
    incident.resolution = data.resolution.strip()
    incident.resolved_by = user.id
    incident.resolved_at = datetime.now(timezone.utc)
    audit(db, user_id=user.id, action="TRANSPORT_INCIDENT_RESOLVE", entity_type="TRANSPORT_INCIDENT",
          entity_id=incident.id, after=data.model_dump(mode="json"))
    db.commit()
    return {"id": incident.id, "status": incident.status}
