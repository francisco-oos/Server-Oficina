"""Resolución de identidades y expedientes por dominio.

Este módulo concentra dos cosas que el encargo separa explícitamente:

1. **Búsqueda transversal** (apartado 10). Un mismo término —``123456``— puede
   ser el ID laboral de una persona, la serie de un radio, el IMEI de un
   teléfono, el número económico de una unidad o el QR de un nodo. La búsqueda
   localiza todo eso y dice *a qué ficha* llevar cada resultado.

2. **Expedientes por dominio** (apartados 2, 3, 4 y 5). Deliberadamente NO
   existe una ficha universal. Una persona, un nodo, un activo genérico y una
   unidad de transporte comparten Tracking Core por debajo, pero su ciclo de
   vida y su pantalla son distintos, y este módulo construye cada uno con las
   secciones que su dominio necesita.

La regla que gobierna todo el archivo: *todo tiene trazabilidad* no significa
*todo tiene la misma interfaz*.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Asset, AssetCustody, AssetHealthObservation, AssetIdentifier, AssetMovement, AssetTechnology, AssetType,
    AttendanceRecord, CaseRecord, ContractPeriod, EmploymentEngagement, EmploymentLifecycleEvent,
    EngagementOrganizationLink, EppRequest, EvidenceRecord, GroupAssignment, InventoryCount, InventorySession,
    Location, MaintenanceOrder, MaintenancePart, NodeOperation, NodeOperationItem, OperationalEvent,
    Organization, Person, PersonAssignment, PersonHRProfile, Project, TrainingCourse, TrainingRecord,
    TransportAssignment, TransportChecklist, TransportIncident, WorkGroup,
)

#: Tipos de ficha que la interfaz sabe abrir. El backend devuelve uno de éstos
#: junto a cada resultado de búsqueda para que la UI no tenga que adivinar.
DOSSIER_PERSON = "person"
DOSSIER_NODE = "node"
DOSSIER_ASSET = "asset"
DOSSIER_TRANSPORT = "transport-unit"


def asset_label(db: Session, asset: Asset | None) -> str:
    """Etiqueta con la que el operador reconoce un activo.

    Prioriza el número interno/económico sobre la serie porque es lo que se
    grita por radio y lo que aparece rotulado en el equipo. El UUID sólo se usa
    cuando no hay ningún identificador humano.
    """
    if asset is None:
        return "—"
    if asset.internal_code:
        return asset.internal_code
    if asset.serial_number:
        return asset.serial_number
    ident = db.scalar(
        select(AssetIdentifier).where(AssetIdentifier.asset_id == asset.id)
        .order_by(AssetIdentifier.is_primary.desc())
    )
    return ident.value if ident else asset.id


def asset_kind(db: Session, asset: Asset) -> str:
    """Decide qué tipo de ficha corresponde a un activo.

    Se resuelve por **capacidades declaradas del tipo**, nunca por el literal
    del código: registrar mañana un tipo ``NODE_5G`` con capacidad
    ``node_field`` debe abrir la ficha de nodo sin tocar este archivo.
    """
    atype = db.get(AssetType, asset.asset_type_id)
    capabilities = set((atype.capabilities or []) if atype else [])
    if "node_field" in capabilities:
        return DOSSIER_NODE
    if "transport" in capabilities:
        return DOSSIER_TRANSPORT
    return DOSSIER_ASSET


def _identifiers(db: Session, asset_id: str) -> list[dict]:
    rows = db.scalars(select(AssetIdentifier).where(AssetIdentifier.asset_id == asset_id)).all()
    return [{"kind": r.kind, "value": r.value, "is_primary": r.is_primary} for r in rows]


def _name_of(db: Session, model, entity_id: str | None, attr: str = "name") -> str | None:
    if not entity_id:
        return None
    row = db.get(model, entity_id)
    return getattr(row, attr, None) if row else None


# --- Búsqueda transversal ----------------------------------------------------

def search(db: Session, term: str, *, limit: int = 20) -> dict:
    """Busca un término en personas y activos y clasifica cada coincidencia.

    Devuelve resultados ya tipificados (``dossier``) para que la interfaz abra
    la ficha correcta en lugar de intentar mostrar todos los objetos igual.
    El campo ``matched_on`` explica *por qué* coincidió, que es lo que el
    operador necesita para saber si encontró lo que buscaba.
    """
    term = term.strip()
    like = f"%{term}%"
    results: list[dict] = []

    engagement_matches = {
        row.person_id: row.employment_id
        for row in db.scalars(select(EmploymentEngagement).where(EmploymentEngagement.employment_id.ilike(like))).all()
    }
    people = db.scalars(
        select(Person).where(or_(Person.full_name.ilike(like), Person.id.in_(list(engagement_matches) or [""])))
        .order_by(Person.full_name).limit(limit)
    ).all()
    for person in people:
        results.append({
            "dossier": DOSSIER_PERSON, "id": person.id, "label": person.full_name,
            "sublabel": engagement_matches.get(person.id) or "Persona",
            "matched_on": "ID laboral" if person.id in engagement_matches else "Nombre",
            "status": "Activo" if person.active else "Sin relación vigente",
            "tone": "ok" if person.active else "neutral",
        })

    identifier_rows = db.scalars(select(AssetIdentifier).where(AssetIdentifier.value.ilike(like))).all()
    identifier_map: dict[str, str] = {}
    for row in identifier_rows:
        identifier_map.setdefault(row.asset_id, row.kind)
    assets = db.scalars(
        select(Asset).where(or_(
            Asset.internal_code.ilike(like), Asset.serial_number.ilike(like),
            Asset.id.in_(list(identifier_map) or [""]),
        )).limit(limit)
    ).all()
    for asset in assets:
        atype = db.get(AssetType, asset.asset_type_id)
        if asset.id in identifier_map:
            matched = identifier_map[asset.id]
        elif asset.internal_code and term.lower() in asset.internal_code.lower():
            matched = "Número interno / económico"
        else:
            matched = "Número de serie"
        results.append({
            "dossier": asset_kind(db, asset), "id": asset.id, "label": asset_label(db, asset),
            "sublabel": atype.name if atype else "Activo", "matched_on": matched,
            "status": asset.status_code, "tone": "neutral",
        })
    return {"query": term, "count": len(results), "results": results}


# --- Expediente de persona ---------------------------------------------------

def person_summary(db: Session, person_id: str) -> dict | None:
    """Resumen de localización de una persona (apartado 2 del encargo).

    Devuelve exactamente los campos que el encargo pide poder ver de un vistazo
    al localizar personal: estado, grupo, responsable, unidad, conductor, radio,
    teléfono, ubicación y proyecto. Cada uno puede faltar —se devuelve ``None``
    y la interfaz lo muestra como dato no capturado— porque la realidad de campo
    es incompleta y fingir un valor sería peor que admitir el hueco.

    ``conductor`` merece una nota: si la persona consultada ES el conductor
    asignado a su unidad, se indica; si no, se nombra a quien conduce la unidad
    en la que va. Son dos hechos distintos y la interfaz los distingue.
    """
    person = db.get(Person, person_id)
    if person is None:
        return None

    engagement = db.scalar(
        select(EmploymentEngagement).where(EmploymentEngagement.person_id == person_id)
        .order_by(EmploymentEngagement.start_date.desc())
    )
    assignment = db.scalar(
        select(PersonAssignment).where(PersonAssignment.person_id == person_id, PersonAssignment.end_at.is_(None))
        .order_by(PersonAssignment.start_at.desc())
    )
    profile = db.get(PersonHRProfile, person_id)

    project_id = (assignment.project_id if assignment else None) or (engagement.project_id if engagement else None)
    group_id = assignment.group_id if assignment else None
    if group_id is None:
        group_link = db.scalar(
            select(GroupAssignment).where(GroupAssignment.person_id == person_id, GroupAssignment.end_date.is_(None))
        )
        group_id = group_link.group_id if group_link else None

    unit_asset = db.get(Asset, assignment.unit_asset_id) if assignment and assignment.unit_asset_id else None
    driver_name = None
    radio_label = None
    if unit_asset is not None:
        transport = db.scalar(
            select(TransportAssignment).where(
                TransportAssignment.unit_asset_id == unit_asset.id, TransportAssignment.end_at.is_(None)
            ).order_by(TransportAssignment.start_at.desc())
        )
        if transport is not None:
            if transport.driver_person_id:
                driver = db.get(Person, transport.driver_person_id)
                driver_name = driver.full_name if driver else None
            if transport.radio_asset_id:
                radio_label = asset_label(db, db.get(Asset, transport.radio_asset_id))

    if radio_label is None:
        # Radio entregado en custodia directa a la persona. Se resuelve por la
        # CAPACIDAD declarada del tipo (`radio`), nunca por su código: registrar
        # mañana un tipo "RADIO_SATELITAL" debe funcionar sin tocar este archivo.
        for candidate in db.scalars(select(Asset).where(Asset.custodian_person_id == person_id, Asset.active.is_(True))).all():
            atype = db.get(AssetType, candidate.asset_type_id)
            if atype and "radio" in (atype.capabilities or []):
                radio_label = asset_label(db, candidate)
                break

    return {
        "person_id": person.id,
        "full_name": person.full_name,
        "estado": "Activo" if person.active else "Sin relación laboral vigente",
        "employment_id": engagement.employment_id if engagement else None,
        "puesto": engagement.position if engagement else None,
        "grupo": _name_of(db, WorkGroup, group_id),
        "responsable": _name_of(db, Person, assignment.supervisor_person_id, "full_name") if assignment else None,
        "unidad": asset_label(db, unit_asset) if unit_asset else None,
        "unidad_asset_id": unit_asset.id if unit_asset else None,
        "conductor": driver_name,
        "es_conductor": bool(driver_name and unit_asset and driver_name == person.full_name),
        "radio": radio_label,
        "telefono": profile.phone if profile else None,
        "ubicacion": _name_of(db, Location, assignment.location_id) if assignment else None,
        "proyecto": _name_of(db, Project, project_id),
        "categoria": profile.category if profile else None,
    }


def person_dossier(db: Session, person_id: str) -> dict | None:
    """Expediente integral de una persona.

    Estructura deliberadamente distinta a la ficha de un activo: una persona
    tiene vida laboral (altas, bajas, recontrataciones, contratos, outsourcing),
    no custodia ni movimientos de almacén. Los activos aparecen sólo como
    *entregados* a ella, que es el hecho relevante desde RRHH.

    Invariante central: ``person_id`` es estable. Todas las contrataciones,
    incluidas las recontrataciones con otro ID laboral, cuelgan de la misma
    identidad y por eso el expediente puede mostrar la historia completa.
    """
    summary = person_summary(db, person_id)
    if summary is None:
        return None

    engagements = db.scalars(
        select(EmploymentEngagement).where(EmploymentEngagement.person_id == person_id)
        .order_by(EmploymentEngagement.start_date.desc())
    ).all()
    engagement_rows = []
    for eng in engagements:
        organizations = []
        for link in db.scalars(select(EngagementOrganizationLink).where(EngagementOrganizationLink.engagement_id == eng.id)).all():
            org = db.get(Organization, link.organization_id)
            if org:
                organizations.append({"name": org.name, "type": org.organization_type,
                                      "relation": link.relation_type,
                                      "start_date": link.start_date, "end_date": link.end_date})
        engagement_rows.append({
            "id": eng.id, "employment_id": eng.employment_id, "employer_type": eng.employer_type,
            # ``provider`` es texto histórico heredado; convive con la
            # organización normalizada en lugar de borrarse.
            "provider": eng.provider, "position": eng.position, "status": eng.status,
            "start_date": eng.start_date, "end_date": eng.end_date,
            "project": _name_of(db, Project, eng.project_id),
            "organizations": organizations,
            "contract_periods": [
                {"id": c.id, "start_date": c.start_date, "end_date": c.end_date, "source": c.source}
                for c in db.scalars(select(ContractPeriod).where(ContractPeriod.engagement_id == eng.id)
                                    .order_by(ContractPeriod.start_date.desc())).all()
            ],
            "lifecycle": [
                {"event_type": e.event_type, "occurred_on": e.occurred_on, "reason": e.reason}
                for e in db.scalars(select(EmploymentLifecycleEvent)
                                    .where(EmploymentLifecycleEvent.engagement_id == eng.id)
                                    .order_by(EmploymentLifecycleEvent.occurred_on.desc())).all()
            ],
        })

    profile = db.get(PersonHRProfile, person_id)
    hr_profile = None
    if profile is not None:
        hr_profile = {
            "category": profile.category, "license_number": profile.license_number,
            "license_type": profile.license_type, "license_expiry": profile.license_expiry,
            "rotation_on_days": profile.rotation_on_days, "rotation_off_days": profile.rotation_off_days,
            "phone": profile.phone, "emergency_contact": profile.emergency_contact,
            "license_expired": bool(profile.license_expiry and profile.license_expiry < date.today()),
        }

    assignments = db.scalars(
        select(PersonAssignment).where(PersonAssignment.person_id == person_id)
        .order_by(PersonAssignment.start_at.desc()).limit(40)
    ).all()
    attendance = db.scalars(
        select(AttendanceRecord).where(AttendanceRecord.person_id == person_id)
        .order_by(AttendanceRecord.attendance_date.desc()).limit(45)
    ).all()
    courses = {c.id: c.name for c in db.scalars(select(TrainingCourse)).all()}
    training = db.scalars(
        select(TrainingRecord).where(TrainingRecord.person_id == person_id)
        .order_by(TrainingRecord.requested_at.desc()).limit(40)
    ).all()
    epp = db.scalars(
        select(EppRequest).where(EppRequest.person_id == person_id)
        .order_by(EppRequest.requested_at.desc()).limit(40)
    ).all()
    cases = db.scalars(
        select(CaseRecord).where(CaseRecord.person_id == person_id)
        .order_by(CaseRecord.reported_at.desc()).limit(40)
    ).all()

    # Activos entregados: lo que la persona tiene en custodia hoy y lo que tuvo.
    current_assets = db.scalars(select(Asset).where(Asset.custodian_person_id == person_id, Asset.active.is_(True))).all()
    custody_history = db.scalars(
        select(AssetCustody).where(AssetCustody.person_id == person_id)
        .order_by(AssetCustody.start_at.desc()).limit(40)
    ).all()

    # Excepciones de nodos en las que esta persona figura como responsable. Es
    # un hecho trazable, NO una imputación: por eso se etiqueta como reportado.
    node_exceptions = []
    for item in db.scalars(
        select(NodeOperationItem).where(
            NodeOperationItem.responsible_person_id == person_id,
            NodeOperationItem.result_code.is_not(None), NodeOperationItem.result_code != "OK",
        ).limit(40)
    ).all():
        operation = db.get(NodeOperation, item.operation_id)
        node_exceptions.append({
            "asset_id": item.asset_id, "asset_label": asset_label(db, db.get(Asset, item.asset_id)),
            "result_code": item.result_code, "new_status_code": item.new_status_code,
            "occurred_at": operation.occurred_at if operation else None,
            "operation_type": operation.operation_type if operation else None,
            "note": item.note,
        })

    timeline = db.scalars(
        select(OperationalEvent).where(OperationalEvent.entity_type == "PERSON", OperationalEvent.entity_id == person_id)
        .order_by(OperationalEvent.occurred_at.desc()).limit(80)
    ).all()
    evidence = db.scalars(
        select(EvidenceRecord).where(EvidenceRecord.entity_type == "PERSON", EvidenceRecord.entity_id == person_id)
        .order_by(EvidenceRecord.created_at.desc()).limit(30)
    ).all()

    return {
        "summary": summary,
        "hr_profile": hr_profile,
        "engagements": engagement_rows,
        "assignments": [
            {"id": a.id, "project": _name_of(db, Project, a.project_id), "group": _name_of(db, WorkGroup, a.group_id),
             "location": _name_of(db, Location, a.location_id), "role_name": a.role_name,
             "supervisor": _name_of(db, Person, a.supervisor_person_id, "full_name"),
             "unit": asset_label(db, db.get(Asset, a.unit_asset_id)) if a.unit_asset_id else None,
             "start_at": a.start_at, "end_at": a.end_at, "current": a.end_at is None}
            for a in assignments
        ],
        "attendance": [{"date": a.attendance_date, "status": a.status, "imported": bool(a.import_batch_id)} for a in attendance],
        "training": [
            {"id": t.id, "course": courses.get(t.course_id, t.course_id), "state": t.state,
             "scheduled_for": t.scheduled_for, "completed_at": t.completed_at, "note": t.note}
            for t in training
        ],
        "epp": [
            {"id": e.id, "item_type": e.item_type, "reason": e.reason, "status": e.status,
             "requested_at": e.requested_at, "review_note": e.review_note}
            for e in epp
        ],
        "cases": [
            {"id": c.id, "case_type": c.case_type, "summary": c.summary, "status": c.status,
             "resolution": c.resolution, "reported_at": c.reported_at}
            for c in cases
        ],
        "assets_current": [
            {"id": a.id, "label": asset_label(db, a), "type": _name_of(db, AssetType, a.asset_type_id),
             "status": a.status_code, "dossier": asset_kind(db, a)}
            for a in current_assets
        ],
        "assets_history": [
            {"asset_id": c.asset_id, "label": asset_label(db, db.get(Asset, c.asset_id)),
             "assignment_type": c.assignment_type, "start_at": c.start_at, "end_at": c.end_at,
             "returned": c.end_at is not None, "note": c.note}
            for c in custody_history
        ],
        "node_exceptions": node_exceptions,
        "evidence": [
            {"id": e.id, "name": e.original_name, "source": e.source, "sha256": e.sha256, "created_at": e.created_at}
            for e in evidence
        ],
        "timeline": [
            {"event_type": e.event_type, "occurred_at": e.occurred_at, "recorded_at": e.recorded_at,
             "source_type": e.source_type, "payload": e.payload}
            for e in timeline
        ],
    }


# --- Expediente de activo (base común) ---------------------------------------

def _asset_header(db: Session, asset: Asset) -> dict:
    """Cabecera común a toda ficha de activo.

    Es la parte que SÍ comparten todos los activos: identidad, tipo, ubicación
    y custodia. Lo que cambia entre dominios son las secciones que se apilan
    debajo, no esta cabecera.
    """
    atype = db.get(AssetType, asset.asset_type_id)
    technology = db.get(AssetTechnology, asset.technology_id) if asset.technology_id else None
    custodian = db.get(Person, asset.custodian_person_id) if asset.custodian_person_id else None
    return {
        "id": asset.id,
        "label": asset_label(db, asset),
        "dossier": asset_kind(db, asset),
        "type_code": atype.code if atype else None,
        "type_name": atype.name if atype else None,
        "capabilities": list(atype.capabilities or []) if atype else [],
        "technology": technology.name if technology else None,
        "vendor": technology.vendor if technology else None,
        "internal_code": asset.internal_code,
        "serial_number": asset.serial_number,
        "identifiers": _identifiers(db, asset.id),
        "status_code": asset.status_code,
        "condition_code": asset.condition_code,
        "project": _name_of(db, Project, asset.current_project_id),
        "group": _name_of(db, WorkGroup, asset.current_group_id),
        "location": _name_of(db, Location, asset.current_location_id),
        "custodian": custodian.full_name if custodian else None,
        "custodian_person_id": asset.custodian_person_id,
        "active": asset.active,
        "notes": asset.notes,
        "metadata": asset.metadata_json or {},
    }


def _asset_movements(db: Session, asset_id: str, limit: int = 60) -> list[dict]:
    rows = db.scalars(
        select(AssetMovement).where(AssetMovement.asset_id == asset_id)
        .order_by(AssetMovement.occurred_at.desc()).limit(limit)
    ).all()
    return [
        {"id": m.id, "movement_type": m.movement_type, "status_after": m.status_after,
         # occurred_at ≠ recorded_at: el desfase entre campo y captura se
         # conserva y se muestra, nunca se colapsa a una sola fecha.
         "occurred_at": m.occurred_at, "recorded_at": m.recorded_at,
         "project": _name_of(db, Project, m.project_id), "group": _name_of(db, WorkGroup, m.group_id),
         "location": _name_of(db, Location, m.location_id),
         "responsible": _name_of(db, Person, m.responsible_person_id, "full_name"),
         "line_code": m.line_code, "stake_code": m.stake_code,
         "source_type": m.source_type, "source_id": m.source_id, "note": m.note}
        for m in rows
    ]


def _asset_custody(db: Session, asset_id: str, limit: int = 40) -> list[dict]:
    rows = db.scalars(
        select(AssetCustody).where(AssetCustody.asset_id == asset_id)
        .order_by(AssetCustody.start_at.desc()).limit(limit)
    ).all()
    return [
        {"person": _name_of(db, Person, c.person_id, "full_name"), "person_id": c.person_id,
         "assignment_type": c.assignment_type, "project": _name_of(db, Project, c.project_id),
         "location": _name_of(db, Location, c.location_id),
         "start_at": c.start_at, "end_at": c.end_at, "current": c.end_at is None, "note": c.note}
        for c in rows
    ]


def _asset_maintenance(db: Session, asset_id: str) -> list[dict]:
    rows = db.scalars(
        select(MaintenanceOrder).where(MaintenanceOrder.asset_id == asset_id)
        .order_by(MaintenanceOrder.opened_at.desc()).limit(30)
    ).all()
    out = []
    for order in rows:
        parts = db.scalars(select(MaintenancePart).where(MaintenancePart.maintenance_order_id == order.id)).all()
        out.append({
            "id": order.id, "status": order.status, "priority": order.priority, "symptom": order.symptom,
            "fault_code": order.fault_code, "diagnosis": order.diagnosis, "action_taken": order.action_taken,
            "result": order.result, "opened_at": order.opened_at, "closed_at": order.closed_at,
            "downtime_minutes": order.downtime_minutes,
            "parts": [{"component_type": p.component_type, "serial_removed": p.serial_removed,
                       "serial_installed": p.serial_installed, "quantity": p.quantity, "note": p.note} for p in parts],
        })
    return out


def _asset_health(db: Session, asset_id: str) -> list[dict]:
    rows = db.scalars(
        select(AssetHealthObservation).where(AssetHealthObservation.asset_id == asset_id)
        .order_by(AssetHealthObservation.observed_at.desc()).limit(20)
    ).all()
    # Predicción ≠ hecho: estas observaciones se muestran siempre etiquetadas
    # con su fuente y confianza, y nunca alteran el estado factual del activo.
    return [
        {"observed_at": h.observed_at, "source": h.source, "soh_percent": h.soh_percent,
         "rul_days": h.rul_days, "health_score": h.health_score, "confidence": h.confidence,
         "cycles": h.cycles, "operating_hours": h.operating_hours}
        for h in rows
    ]


def _asset_inventory(db: Session, asset_id: str) -> list[dict]:
    rows = db.scalars(
        select(InventoryCount).where(InventoryCount.asset_id == asset_id)
        .order_by(InventoryCount.counted_at.desc()).limit(20)
    ).all()
    out = []
    for count in rows:
        session_row = db.get(InventorySession, count.session_id)
        out.append({
            "session": session_row.name if session_row else count.session_id,
            "session_status": session_row.status if session_row else None,
            "found": count.found, "observed_status_code": count.observed_status_code,
            "location": _name_of(db, Location, count.location_id),
            "counted_at": count.counted_at, "note": count.note,
        })
    return out


def _asset_evidence(db: Session, asset_id: str) -> list[dict]:
    rows = db.scalars(
        select(EvidenceRecord).where(EvidenceRecord.entity_type == "ASSET", EvidenceRecord.entity_id == asset_id)
        .order_by(EvidenceRecord.created_at.desc()).limit(30)
    ).all()
    return [{"id": e.id, "name": e.original_name, "source": e.source, "sha256": e.sha256,
             "size_bytes": e.size_bytes, "created_at": e.created_at} for e in rows]


def _asset_timeline(db: Session, asset_id: str) -> list[dict]:
    rows = db.scalars(
        select(OperationalEvent).where(OperationalEvent.entity_type == "ASSET", OperationalEvent.entity_id == asset_id)
        .order_by(OperationalEvent.occurred_at.desc()).limit(80)
    ).all()
    return [{"event_type": e.event_type, "occurred_at": e.occurred_at, "recorded_at": e.recorded_at,
             "source_type": e.source_type, "payload": e.payload} for e in rows]


def asset_dossier(db: Session, asset_id: str) -> dict | None:
    """Ficha de un activo genérico: radio, antena, computadora, teléfono, dron…

    Centrada en lo que el apartado 4 del encargo pide: identidad, custodia,
    entregas, transferencias, devoluciones, inventarios, mantenimiento y
    evidencia. Sin secciones de operación de campo, que no le corresponden.
    """
    asset = db.get(Asset, asset_id)
    if asset is None:
        return None
    return {
        "kind": DOSSIER_ASSET,
        "header": _asset_header(db, asset),
        "custody": _asset_custody(db, asset_id),
        "movements": _asset_movements(db, asset_id),
        "maintenance": _asset_maintenance(db, asset_id),
        "health": _asset_health(db, asset_id),
        "inventory": _asset_inventory(db, asset_id),
        "evidence": _asset_evidence(db, asset_id),
        "timeline": _asset_timeline(db, asset_id),
    }


def node_dossier(db: Session, asset_id: str) -> dict | None:
    """Ficha de un nodo sísmico (apartado 3 del encargo).

    Un nodo NO se reduce a un campo ``estado``. Además de la cabecera común
    lleva su ciclo operacional: en qué operaciones/lotes participó, con qué
    resultado, en qué línea y estaca, quién lo manejaba y qué excepciones
    acumuló. El estado actual es una *derivación* de ese historial, y se
    presenta junto a él para que se pueda auditar de dónde sale.

    Responde a la pregunta del encargo: dónde estuvo, qué ocurrió, quién
    intervino y cuál es su situación actual.
    """
    asset = db.get(Asset, asset_id)
    if asset is None:
        return None

    items = db.scalars(
        select(NodeOperationItem).where(NodeOperationItem.asset_id == asset_id).limit(120)
    ).all()
    operations = []
    exceptions = []
    for item in items:
        operation = db.get(NodeOperation, item.operation_id)
        if operation is None:
            continue
        participants = [
            name for name in (
                _name_of(db, Person, pid, "full_name") for pid in (operation.participant_person_ids or [])
            ) if name
        ]
        row = {
            "operation_id": operation.id, "operation_type": operation.operation_type,
            "occurred_at": operation.occurred_at, "recorded_at": operation.recorded_at,
            "project": _name_of(db, Project, operation.project_id),
            "group": _name_of(db, WorkGroup, operation.group_id),
            "location": _name_of(db, Location, operation.location_id),
            "line_code": operation.line_code, "stake_from": item.stake_from, "stake_to": item.stake_to,
            "result_code": item.result_code,
            "previous_status_code": item.previous_status_code, "new_status_code": item.new_status_code,
            "responsible": _name_of(db, Person, item.responsible_person_id, "full_name"),
            "participants": participants,
            "source_type": operation.source_type, "source_id": operation.source_id,
            "note": item.note or operation.note,
        }
        operations.append(row)
        if item.result_code and item.result_code != "OK":
            exceptions.append(row)
    operations.sort(key=lambda r: r["occurred_at"], reverse=True)
    exceptions.sort(key=lambda r: r["occurred_at"], reverse=True)

    header = _asset_header(db, asset)
    last_movement = db.scalar(
        select(AssetMovement).where(AssetMovement.asset_id == asset_id).order_by(AssetMovement.occurred_at.desc())
    )
    return {
        "kind": DOSSIER_NODE,
        "header": header,
        # Estado actual ≠ historial: se expone explícitamente de dónde se
        # derivó el estado vigente en lugar de presentarlo como un dato suelto.
        "current_state": {
            "status_code": asset.status_code,
            "derived_from": {
                "movement_type": last_movement.movement_type if last_movement else None,
                "occurred_at": last_movement.occurred_at if last_movement else None,
                "line_code": last_movement.line_code if last_movement else None,
                "stake_code": last_movement.stake_code if last_movement else None,
                "responsible": _name_of(db, Person, last_movement.responsible_person_id, "full_name") if last_movement else None,
            } if last_movement else None,
            "location": header["location"],
            "project": header["project"],
        },
        "operations": operations,
        "exceptions": exceptions,
        "movements": _asset_movements(db, asset_id),
        "custody": _asset_custody(db, asset_id),
        "maintenance": _asset_maintenance(db, asset_id),
        "health": _asset_health(db, asset_id),
        "inventory": _asset_inventory(db, asset_id),
        "evidence": _asset_evidence(db, asset_id),
        "timeline": _asset_timeline(db, asset_id),
    }


def transport_dossier(db: Session, asset_id: str) -> dict | None:
    """Ficha de una unidad de transporte (apartado 5 del encargo).

    Transporte no es otro inventario genérico: la unidad se presenta por su
    conductor, su grupo, su radio y teléfono asociados, su disponibilidad, su
    checklist y sus incidencias. El material de almacén queda debajo, no arriba.
    """
    asset = db.get(Asset, asset_id)
    if asset is None:
        return None

    assignments = db.scalars(
        select(TransportAssignment).where(TransportAssignment.unit_asset_id == asset_id)
        .order_by(TransportAssignment.start_at.desc()).limit(40)
    ).all()
    current = next((a for a in assignments if a.end_at is None), None)
    checklists = db.scalars(
        select(TransportChecklist).where(TransportChecklist.unit_asset_id == asset_id)
        .order_by(TransportChecklist.occurred_at.desc()).limit(30)
    ).all()
    incidents = db.scalars(
        select(TransportIncident).where(TransportIncident.unit_asset_id == asset_id)
        .order_by(TransportIncident.occurred_at.desc()).limit(30)
    ).all()

    def _assignment_row(row: TransportAssignment) -> dict:
        return {
            "id": row.id,
            "driver": _name_of(db, Person, row.driver_person_id, "full_name"),
            "driver_person_id": row.driver_person_id,
            "project": _name_of(db, Project, row.project_id),
            "group": _name_of(db, WorkGroup, row.group_id),
            "location": _name_of(db, Location, row.location_id),
            "radio": asset_label(db, db.get(Asset, row.radio_asset_id)) if row.radio_asset_id else None,
            "phone": asset_label(db, db.get(Asset, row.phone_asset_id)) if row.phone_asset_id else None,
            "availability": row.availability,
            "start_at": row.start_at, "end_at": row.end_at, "current": row.end_at is None,
            "note": row.note,
        }

    return {
        "kind": DOSSIER_TRANSPORT,
        "header": _asset_header(db, asset),
        "current_assignment": _assignment_row(current) if current else None,
        "assignments": [_assignment_row(a) for a in assignments],
        "checklists": [
            {"id": c.id, "result": c.result, "odometer_km": c.odometer_km, "fuel_level": c.fuel_level,
             "driver": _name_of(db, Person, c.driver_person_id, "full_name"),
             "occurred_at": c.occurred_at, "recorded_at": c.recorded_at,
             "items": c.items_json or [], "note": c.note}
            for c in checklists
        ],
        "incidents": [
            {"id": i.id, "incident_type": i.incident_type, "severity": i.severity, "summary": i.summary,
             "status": i.status, "occurred_at": i.occurred_at, "recorded_at": i.recorded_at,
             "driver": _name_of(db, Person, i.driver_person_id, "full_name"),
             "location": _name_of(db, Location, i.location_id),
             "resolution": i.resolution, "resolved_at": i.resolved_at,
             "maintenance_order_id": i.maintenance_order_id}
            for i in incidents
        ],
        "maintenance": _asset_maintenance(db, asset_id),
        "health": _asset_health(db, asset_id),
        "movements": _asset_movements(db, asset_id),
        "evidence": _asset_evidence(db, asset_id),
        "timeline": _asset_timeline(db, asset_id),
    }


#: Despachador de expedientes por tipo de ficha. La interfaz pide un tipo y
#: recibe la estructura que corresponde a ese dominio, nunca una ficha genérica.
DOSSIER_BUILDERS = {
    DOSSIER_NODE: node_dossier,
    DOSSIER_ASSET: asset_dossier,
    DOSSIER_TRANSPORT: transport_dossier,
}


def build_asset_dossier(db: Session, asset_id: str) -> dict | None:
    """Construye la ficha correcta para un activo según sus capacidades."""
    asset = db.get(Asset, asset_id)
    if asset is None:
        return None
    return DOSSIER_BUILDERS[asset_kind(db, asset)](db, asset_id)
