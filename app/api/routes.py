from __future__ import annotations

import csv
import hashlib
import io
import mimetypes
import os
import re
import shutil
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import current_user, require
from app.core.config import load_settings
from app.core.security import create_session, destroy_session, hash_password, permission_codes, verify_password
from app.db.base import get_db
from app.db.models import (
    Asset, AssetCustody, AssetHealthObservation, AssetIdentifier, AssetMovement, AssetTechnology, AssetType,
    AttendanceRecord, AuditLog, CaseRecord, CatalogItem, ContractPeriod, EmploymentEngagement, EmploymentLifecycleEvent,
    EngagementOrganizationLink, EppHistory, EppRequest, Evidence, EvidenceRecord, EvidenceRepository, GroupAssignment,
    ImportBatch, ImportIssue, InventoryCount, InventorySession, Location, MaintenanceOrder, MaintenancePart,
    NodeOperation, NodeOperationItem, OperationalEvent, Organization, Permission, Person, PersonAssignment,
    PersonHRProfile, Project, ProjectCloseout, Role, TrainingCourse, TrainingRecord, User, WorkGroup
)
from app.services.audit import audit
from app.services.events import record_event
from app.services.imports import commit_import, normalize_text, preview_import

router = APIRouter(prefix="/api")

class LoginIn(BaseModel):
    username: str
    password: str

class FirstAdminIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=10)

class PersonIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=240)
    employment_id: str = Field(min_length=1, max_length=80)
    position: str | None = None
    employer_type: str = "DIRECT"
    provider: str | None = None
    start_date: date
    project_id: str | None = None

class RehireIn(BaseModel):
    employment_id: str
    position: str | None = None
    employer_type: str = "DIRECT"
    provider: str | None = None
    start_date: date
    project_id: str | None = None

class EppRequestIn(BaseModel):
    person_id: str
    item_type: str
    reason: str

class EppReviewIn(BaseModel):
    decision: str
    note: str = ""

class CourseIn(BaseModel):
    code: str
    name: str

class TrainingScheduleIn(BaseModel):
    person_id: str
    course_id: str
    scheduled_for: date | None = None
    note: str | None = None

class CaseIn(BaseModel):
    person_id: str | None = None
    case_type: str
    summary: str

class CaseResolveIn(BaseModel):
    resolution: str

class ProjectIn(BaseModel):
    code: str
    name: str
    start_date: date | None = None

class GroupIn(BaseModel):
    code: str
    name: str
    project_id: str | None = None

class UserCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=10)
    roles: list[str] = Field(min_length=1)

class EndEngagementIn(BaseModel):
    end_date: date
    reason: str | None = None

class ContractPeriodIn(BaseModel):
    start_date: date
    end_date: date | None = None
    source: str | None = None



class RoleCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = ""
    permissions: list[str] = Field(default_factory=list)

class UserRolesIn(BaseModel):
    roles: list[str] = Field(min_length=1)

class CatalogItemIn(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=180)
    description: str = ""
    active: bool = True
    sort_order: int = 100
    metadata: dict = Field(default_factory=dict)

class OrganizationIn(BaseModel):
    code: str
    name: str
    organization_type: str = "COMPANY"
    metadata: dict = Field(default_factory=dict)

class EngagementOrganizationIn(BaseModel):
    organization_id: str
    relation_type: str = "EMPLOYER"
    start_date: date | None = None
    end_date: date | None = None

class LocationIn(BaseModel):
    code: str
    name: str
    location_type: str = "OTHER"
    project_id: str | None = None
    parent_id: str | None = None
    metadata: dict = Field(default_factory=dict)

class HRProfileIn(BaseModel):
    category: str | None = None
    license_number: str | None = None
    license_type: str | None = None
    license_expiry: date | None = None
    rotation_on_days: int | None = Field(default=None, ge=0, le=365)
    rotation_off_days: int | None = Field(default=None, ge=0, le=365)
    phone: str | None = None
    emergency_contact: str | None = None
    metadata: dict = Field(default_factory=dict)

class PersonAssignmentIn(BaseModel):
    project_id: str | None = None
    group_id: str | None = None
    location_id: str | None = None
    supervisor_person_id: str | None = None
    unit_asset_id: str | None = None
    role_name: str | None = None
    start_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)

class AttendanceIn(BaseModel):
    person_id: str
    attendance_date: date
    status: str

class LifecycleEventIn(BaseModel):
    event_type: str
    occurred_on: date
    reason: str | None = None
    metadata: dict = Field(default_factory=dict)

class AssetTypeIn(BaseModel):
    code: str
    name: str
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

class AssetTechnologyIn(BaseModel):
    code: str
    name: str
    vendor: str | None = None
    metadata: dict = Field(default_factory=dict)

class AssetIdentifierIn(BaseModel):
    kind: str
    value: str
    is_primary: bool = False

class AssetIn(BaseModel):
    type_code: str
    technology_code: str | None = None
    internal_code: str | None = None
    serial_number: str | None = None
    status_code: str = "AVAILABLE"
    condition_code: str | None = None
    project_id: str | None = None
    group_id: str | None = None
    location_id: str | None = None
    custodian_person_id: str | None = None
    notes: str | None = None
    identifiers: list[AssetIdentifierIn] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

class AssetMoveIn(BaseModel):
    movement_type: str
    status_after: str | None = None
    project_id: str | None = None
    group_id: str | None = None
    location_id: str | None = None
    responsible_person_id: str | None = None
    line_code: str | None = None
    stake_code: str | None = None
    occurred_at: datetime | None = None
    participant_person_ids: list[str] = Field(default_factory=list)
    source_type: str = "UI"
    source_id: str | None = None
    note: str | None = None
    metadata: dict = Field(default_factory=dict)

class NodeOperationItemIn(BaseModel):
    asset_id: str
    stake_from: str | None = None
    stake_to: str | None = None
    result_code: str | None = None
    responsible_person_id: str | None = None
    note: str | None = None
    metadata: dict = Field(default_factory=dict)

class NodeOperationIn(BaseModel):
    operation_type: str
    project_id: str | None = None
    group_id: str | None = None
    location_id: str | None = None
    line_code: str | None = None
    occurred_at: datetime | None = None
    participant_person_ids: list[str] = Field(default_factory=list)
    source_type: str = "UI"
    source_id: str | None = None
    note: str | None = None
    metadata: dict = Field(default_factory=dict)
    items: list[NodeOperationItemIn] = Field(min_length=1)

class MaintenanceOpenIn(BaseModel):
    asset_id: str
    priority: str = "NORMAL"
    symptom: str | None = None
    fault_code: str | None = None
    metadata: dict = Field(default_factory=dict)

class MaintenanceUpdateIn(BaseModel):
    status: str | None = None
    diagnosis: str | None = None
    action_taken: str | None = None
    result: str | None = None
    close: bool = False
    status_after: str | None = None
    downtime_minutes: int | None = Field(default=None, ge=0)
    metadata: dict = Field(default_factory=dict)

class MaintenancePartIn(BaseModel):
    component_type: str
    serial_removed: str | None = None
    serial_installed: str | None = None
    quantity: int = Field(default=1, ge=1)
    note: str | None = None

class HealthObservationIn(BaseModel):
    observed_at: datetime | None = None
    source: str = "MANUAL"
    soh_percent: int | None = Field(default=None, ge=0, le=100)
    rul_days: int | None = Field(default=None, ge=0)
    health_score: int | None = Field(default=None, ge=0, le=100)
    confidence: str | None = None
    cycles: int | None = Field(default=None, ge=0)
    operating_hours: int | None = Field(default=None, ge=0)
    payload: dict = Field(default_factory=dict)

class InventorySessionIn(BaseModel):
    name: str
    project_id: str | None = None
    location_id: str | None = None
    notes: str | None = None

class InventoryCountIn(BaseModel):
    asset_id: str
    found: bool = True
    observed_status_code: str | None = None
    location_id: str | None = None
    note: str | None = None

class ProjectCloseoutIn(BaseModel):
    end_date: date | None = None
    note: str | None = None


class EvidenceRepositoryIn(BaseModel):
    code: str
    name: str
    repository_type: str = "LOCAL"
    mount_point: str
    canonical_uri: str | None = None
    metadata: dict = Field(default_factory=dict)

@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"ok": True, "service": "server-oficina", "version": __version__, "time": datetime.now(timezone.utc).isoformat()}

@router.get("/setup/status")
def setup_status(db: Session = Depends(get_db)):
    return {"needs_setup": (db.scalar(select(func.count()).select_from(User)) or 0) == 0}

@router.post("/setup/first-admin")
def first_admin(data: FirstAdminIn, db: Session = Depends(get_db)):
    if (db.scalar(select(func.count()).select_from(User)) or 0) != 0:
        raise HTTPException(409, "La configuración inicial ya fue completada")
    role = db.scalar(select(Role).where(Role.name == "ADMIN"))
    if not role:
        raise HTTPException(500, "RBAC no inicializado")
    user = User(username=data.username.strip().lower(), display_name=data.display_name.strip(), password_hash=hash_password(data.password), roles=[role])
    db.add(user); db.commit(); db.refresh(user)
    return {"id": user.id, "username": user.username}

@router.post("/auth/login")
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username.strip().lower()))
    if not user or not user.active or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Credenciales inválidas")
    token = create_session(db, user)
    response.set_cookie("session_id", token, httponly=True, samesite="lax", secure=load_settings().cookie_secure, max_age=load_settings().session_hours * 3600)
    return {"user": {"id": user.id, "username": user.username, "display_name": user.display_name, "permissions": sorted(permission_codes(user))}}

@router.post("/auth/logout")
def logout(response: Response, session_id: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    destroy_session(db, session_id); response.delete_cookie("session_id"); return {"ok": True}

@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "roles": [r.name for r in user.roles], "permissions": sorted(permission_codes(user))}

@router.get("/users")
def list_users(db: Session = Depends(get_db), user: User = Depends(require("users.manage"))):
    items = db.scalars(select(User).order_by(User.username)).all()
    return [{"id": x.id, "username": x.username, "display_name": x.display_name, "active": x.active, "roles": [r.name for r in x.roles]} for x in items]

@router.post("/users")
def create_user(data: UserCreateIn, db: Session = Depends(get_db), user: User = Depends(require("users.manage"))):
    username = data.username.strip().lower()
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(409, "Usuario ya existe")
    roles = db.scalars(select(Role).where(Role.name.in_([r.upper() for r in data.roles]))).all()
    if len(roles) != len(set(r.upper() for r in data.roles)):
        raise HTTPException(422, "Uno o más roles no existen")
    item = User(username=username, display_name=data.display_name.strip(), password_hash=hash_password(data.password), roles=list(roles))
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "username": item.username, "roles": [r.name for r in item.roles]}

@router.get("/roles")
def list_roles(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [{"name": r.name, "description": r.description, "permissions": sorted(p.code for p in r.permissions)} for r in db.scalars(select(Role).order_by(Role.name)).all()]

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require("dashboard.view"))):
    persons = db.scalar(select(func.count()).select_from(Person).where(Person.active.is_(True))) or 0
    pending_epp = db.scalar(select(func.count()).select_from(EppRequest).where(EppRequest.status == "PENDING")) or 0
    open_cases = db.scalar(select(func.count()).select_from(CaseRecord).where(CaseRecord.status == "OPEN")) or 0
    wait_training = db.scalar(select(func.count()).select_from(TrainingRecord).where(TrainingRecord.state.in_(["WAITLIST", "SCHEDULED"]))) or 0
    assets_total = db.scalar(select(func.count()).select_from(Asset).where(Asset.active.is_(True))) or 0
    maintenance_open = db.scalar(select(func.count()).select_from(MaintenanceOrder).where(MaintenanceOrder.status != "CLOSED")) or 0
    critical_codes = [x.code for x in db.scalars(select(CatalogItem).where(CatalogItem.catalog == "ASSET_STATUS", CatalogItem.active.is_(True))).all() if (x.metadata_json or {}).get("critical")]
    critical_assets = db.scalar(select(func.count()).select_from(Asset).where(Asset.active.is_(True), Asset.status_code.in_(critical_codes))) or 0 if critical_codes else 0
    status_rows = db.execute(select(Asset.status_code, func.count()).where(Asset.active.is_(True)).group_by(Asset.status_code)).all()
    recent = db.scalars(select(OperationalEvent).order_by(OperationalEvent.recorded_at.desc()).limit(16)).all()
    return {"active_persons": persons, "pending_epp": pending_epp, "open_cases": open_cases, "pending_training": wait_training,
            "assets_total": assets_total, "critical_assets": critical_assets, "maintenance_open": maintenance_open,
            "assets_by_status": {code: count for code, count in status_rows},
            "recent_events": [{"type": e.event_type, "entity_type": e.entity_type, "entity_id": e.entity_id, "occurred_at": e.occurred_at, "recorded_at": e.recorded_at} for e in recent]}

@router.get("/persons")
def persons(q: str = "", db: Session = Depends(get_db), user: User = Depends(require("person.view"))):
    stmt = select(Person).order_by(Person.full_name).limit(100)
    if q.strip():
        term = f"%{q.strip()}%"
        engagement_ids = select(EmploymentEngagement.person_id).where(EmploymentEngagement.employment_id.ilike(term))
        stmt = select(Person).where(or_(Person.full_name.ilike(term), Person.id.in_(engagement_ids))).order_by(Person.full_name).limit(100)
    items = db.scalars(stmt).all()
    result = []
    for p in items:
        eng = db.scalar(select(EmploymentEngagement).where(EmploymentEngagement.person_id == p.id).order_by(EmploymentEngagement.start_date.desc()))
        assignment = db.scalar(select(GroupAssignment).where(GroupAssignment.person_id == p.id, GroupAssignment.end_date.is_(None)))
        group = db.get(WorkGroup, assignment.group_id) if assignment else None
        result.append({"id": p.id, "full_name": p.full_name, "active": p.active, "employment_id": eng.employment_id if eng else None, "position": eng.position if eng else None, "group": group.name if group else None})
    return result

@router.post("/persons")
def create_person(data: PersonIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("person.edit"))):
    if db.scalar(select(EmploymentEngagement).where(EmploymentEngagement.employment_id == data.employment_id, EmploymentEngagement.end_date.is_(None))):
        raise HTTPException(409, "ID laboral activo ya registrado")
    p = Person(full_name=data.full_name.strip(), normalized_name=normalize_text(data.full_name))
    db.add(p); db.flush()
    eng = EmploymentEngagement(person_id=p.id, employment_id=data.employment_id.strip(), employer_type=data.employer_type, provider=data.provider, position=data.position, project_id=data.project_id, start_date=data.start_date)
    db.add(eng)
    record_event(db, entity_type="PERSON", entity_id=p.id, event_type="PERSON_CREATED", occurred_at=datetime.combine(data.start_date, datetime.min.time(), tzinfo=timezone.utc), project_id=data.project_id, actor_user_id=user.id, payload={"employment_id": data.employment_id})
    audit(db, user_id=user.id, action="PERSON_CREATE", entity_type="PERSON", entity_id=p.id, after=data.model_dump(mode="json"), ip_address=request.client.host if request.client else None)
    db.commit(); return {"id": p.id}

@router.post("/persons/{person_id}/rehire")
def rehire(person_id: str, data: RehireIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("person.edit"))):
    p = db.get(Person, person_id)
    if not p: raise HTTPException(404, "Persona no encontrada")
    active = db.scalar(select(EmploymentEngagement).where(EmploymentEngagement.person_id == person_id, EmploymentEngagement.end_date.is_(None)))
    if active: raise HTTPException(409, "La persona ya tiene una relación laboral activa")
    eng = EmploymentEngagement(person_id=person_id, employment_id=data.employment_id, employer_type=data.employer_type, provider=data.provider, position=data.position, project_id=data.project_id, start_date=data.start_date)
    db.add(eng); p.active = True
    record_event(db, entity_type="PERSON", entity_id=p.id, event_type="PERSON_REHIRED", occurred_at=datetime.combine(data.start_date, datetime.min.time(), tzinfo=timezone.utc), project_id=data.project_id, actor_user_id=user.id, payload={"employment_id": data.employment_id})
    audit(db, user_id=user.id, action="PERSON_REHIRE", entity_type="PERSON", entity_id=p.id, after=data.model_dump(mode="json"), ip_address=request.client.host if request.client else None)
    db.commit(); return {"id": eng.id}

@router.post("/engagements/{engagement_id}/end")
def end_engagement(engagement_id: str, data: EndEngagementIn, db: Session = Depends(get_db), user: User = Depends(require("person.edit"))):
    eng = db.get(EmploymentEngagement, engagement_id)
    if not eng: raise HTTPException(404, "Relación laboral no encontrada")
    if eng.end_date: raise HTTPException(409, "La relación ya está cerrada")
    if data.end_date < eng.start_date: raise HTTPException(422, "La fecha de baja no puede ser anterior al alta")
    eng.end_date = data.end_date; eng.status = "ENDED"
    person = db.get(Person, eng.person_id)
    remaining = db.scalar(select(EmploymentEngagement).where(EmploymentEngagement.person_id == eng.person_id, EmploymentEngagement.id != eng.id, EmploymentEngagement.end_date.is_(None)))
    if person and not remaining: person.active = False
    record_event(db, entity_type="PERSON", entity_id=eng.person_id, event_type="EMPLOYMENT_ENDED", occurred_at=datetime.combine(data.end_date, datetime.min.time(), tzinfo=timezone.utc), project_id=eng.project_id, actor_user_id=user.id, payload={"engagement_id": eng.id, "employment_id": eng.employment_id, "reason": data.reason})
    audit(db, user_id=user.id, action="EMPLOYMENT_END", entity_type="EMPLOYMENT_ENGAGEMENT", entity_id=eng.id, after={"end_date": data.end_date.isoformat(), "reason": data.reason})
    db.commit(); return {"id": eng.id, "status": eng.status, "end_date": eng.end_date}

@router.post("/engagements/{engagement_id}/contracts")
def add_contract_period(engagement_id: str, data: ContractPeriodIn, db: Session = Depends(get_db), user: User = Depends(require("person.edit"))):
    eng = db.get(EmploymentEngagement, engagement_id)
    if not eng: raise HTTPException(404, "Relación laboral no encontrada")
    if data.end_date and data.end_date < data.start_date: raise HTTPException(422, "Periodo inválido")
    cp = ContractPeriod(engagement_id=engagement_id, start_date=data.start_date, end_date=data.end_date, source=data.source)
    db.add(cp); db.flush()
    record_event(db, entity_type="PERSON", entity_id=eng.person_id, event_type="CONTRACT_PERIOD_ADDED", occurred_at=datetime.combine(data.start_date, datetime.min.time(), tzinfo=timezone.utc), project_id=eng.project_id, actor_user_id=user.id, payload={"engagement_id": eng.id, "contract_period_id": cp.id, "end_date": data.end_date.isoformat() if data.end_date else None})
    db.commit(); return {"id": cp.id}

@router.get("/persons/{person_id}")
def person_detail(person_id: str, db: Session = Depends(get_db), user: User = Depends(require("person.view"))):
    p = db.get(Person, person_id)
    if not p: raise HTTPException(404, "Persona no encontrada")
    engagements = db.scalars(select(EmploymentEngagement).where(EmploymentEngagement.person_id == person_id).order_by(EmploymentEngagement.start_date.desc())).all()
    epp = db.scalars(select(EppRequest).where(EppRequest.person_id == person_id).order_by(EppRequest.requested_at.desc()).limit(30)).all()
    training = db.scalars(select(TrainingRecord).where(TrainingRecord.person_id == person_id).order_by(TrainingRecord.requested_at.desc()).limit(30)).all()
    cases = db.scalars(select(CaseRecord).where(CaseRecord.person_id == person_id).order_by(CaseRecord.reported_at.desc()).limit(30)).all()
    events = db.scalars(select(OperationalEvent).where(OperationalEvent.entity_type == "PERSON", OperationalEvent.entity_id == person_id).order_by(OperationalEvent.occurred_at.desc()).limit(50)).all()
    return {"person": {"id": p.id, "full_name": p.full_name, "active": p.active},
            "engagements": [{"id": x.id, "employment_id": x.employment_id, "employer_type": x.employer_type, "provider": x.provider, "position": x.position, "start_date": x.start_date, "end_date": x.end_date, "status": x.status, "project_id": x.project_id, "contract_periods": [{"id": c.id, "start_date": c.start_date, "end_date": c.end_date, "source": c.source} for c in db.scalars(select(ContractPeriod).where(ContractPeriod.engagement_id == x.id).order_by(ContractPeriod.start_date.desc())).all()]} for x in engagements],
            "epp": [{"id": x.id, "item_type": x.item_type, "reason": x.reason, "status": x.status, "requested_at": x.requested_at, "review_note": x.review_note} for x in epp],
            "training": [{"id": x.id, "course_id": x.course_id, "state": x.state, "scheduled_for": x.scheduled_for, "completed_at": x.completed_at} for x in training],
            "cases": [{"id": x.id, "case_type": x.case_type, "summary": x.summary, "status": x.status, "resolution": x.resolution, "reported_at": x.reported_at} for x in cases],
            "timeline": [{"event_type": x.event_type, "occurred_at": x.occurred_at, "recorded_at": x.recorded_at, "source_type": x.source_type, "payload": x.payload} for x in events]}

@router.post("/epp/requests")
def epp_request(data: EppRequestIn, db: Session = Depends(get_db), user: User = Depends(require("epp.request"))):
    if not db.get(Person, data.person_id): raise HTTPException(404, "Persona no encontrada")
    req = EppRequest(person_id=data.person_id, item_type=data.item_type, reason=data.reason, requested_by=user.id)
    db.add(req); db.flush(); record_event(db, entity_type="PERSON", entity_id=data.person_id, event_type="EPP_REQUESTED", actor_user_id=user.id, payload={"request_id": req.id, "item_type": data.item_type})
    audit(db, user_id=user.id, action="EPP_REQUEST_CREATE", entity_type="EPP_REQUEST", entity_id=req.id, after=data.model_dump(mode="json")); db.commit(); return {"id": req.id, "status": req.status}

@router.get("/epp/requests")
def epp_requests(db: Session = Depends(get_db), user: User = Depends(require("epp.view"))):
    items = db.scalars(select(EppRequest).order_by(EppRequest.requested_at.desc()).limit(100)).all()
    return [{"id": x.id, "person_id": x.person_id, "item_type": x.item_type, "reason": x.reason, "status": x.status, "requested_at": x.requested_at, "review_note": x.review_note} for x in items]

@router.post("/epp/requests/{request_id}/review")
def epp_review(request_id: str, data: EppReviewIn, db: Session = Depends(get_db), user: User = Depends(require("epp.validate_hr"))):
    req = db.get(EppRequest, request_id)
    if not req: raise HTTPException(404, "Solicitud no encontrada")
    decision = data.decision.upper()
    if decision not in {"APPROVED", "REJECTED", "PENDING"}: raise HTTPException(422, "Decisión inválida")
    before = {"status": req.status, "review_note": req.review_note}
    req.status = decision; req.reviewed_by = user.id; req.reviewed_at = datetime.now(timezone.utc); req.review_note = data.note
    if decision == "APPROVED":
        db.add(EppHistory(person_id=req.person_id, item_type=req.item_type, action="APPROVED_REPLACEMENT", request_id=req.id, note=data.note))
    record_event(db, entity_type="PERSON", entity_id=req.person_id, event_type=f"EPP_{decision}", actor_user_id=user.id, payload={"request_id": req.id, "item_type": req.item_type})
    audit(db, user_id=user.id, action="EPP_REVIEW", entity_type="EPP_REQUEST", entity_id=req.id, before=before, after={"status": decision, "review_note": data.note}); db.commit(); return {"id": req.id, "status": req.status}

@router.post("/training/courses")
def create_course(data: CourseIn, db: Session = Depends(get_db), user: User = Depends(require("training.schedule_hr"))):
    course = TrainingCourse(code=data.code.strip().upper(), name=data.name.strip()); db.add(course); db.commit(); db.refresh(course); return {"id": course.id}

@router.get("/training/courses")
def courses(db: Session = Depends(get_db), user: User = Depends(require("training.view"))):
    return [{"id": c.id, "code": c.code, "name": c.name} for c in db.scalars(select(TrainingCourse).order_by(TrainingCourse.name)).all()]

@router.get("/training/records")
def training_records(db: Session = Depends(get_db), user: User = Depends(require("training.view"))):
    items = db.scalars(select(TrainingRecord).order_by(TrainingRecord.requested_at.desc()).limit(200)).all()
    return [{"id": x.id, "person_id": x.person_id, "course_id": x.course_id, "state": x.state, "scheduled_for": x.scheduled_for, "completed_at": x.completed_at, "note": x.note} for x in items]

@router.post("/training/records")
def training_schedule(data: TrainingScheduleIn, db: Session = Depends(get_db), user: User = Depends(require("training.schedule_hr"))):
    state = "SCHEDULED" if data.scheduled_for else "WAITLIST"
    rec = TrainingRecord(person_id=data.person_id, course_id=data.course_id, state=state, requested_by=user.id, scheduled_for=data.scheduled_for, note=data.note)
    db.add(rec); db.flush(); record_event(db, entity_type="PERSON", entity_id=data.person_id, event_type=f"TRAINING_{state}", actor_user_id=user.id, payload={"training_record_id": rec.id, "course_id": data.course_id}); db.commit(); return {"id": rec.id, "state": rec.state}

@router.post("/training/records/{record_id}/complete")
def training_complete(record_id: str, db: Session = Depends(get_db), user: User = Depends(require("training.confirm_hse"))):
    rec = db.get(TrainingRecord, record_id)
    if not rec: raise HTTPException(404, "Registro no encontrado")
    rec.state = "COMPLETED"; rec.completed_at = datetime.now(timezone.utc); rec.confirmed_by = user.id
    record_event(db, entity_type="PERSON", entity_id=rec.person_id, event_type="TRAINING_COMPLETED", actor_user_id=user.id, payload={"training_record_id": rec.id, "course_id": rec.course_id}); db.commit(); return {"id": rec.id, "state": rec.state}

@router.get("/cases")
def list_cases(db: Session = Depends(get_db), user: User = Depends(require("cases.create"))):
    items = db.scalars(select(CaseRecord).order_by(CaseRecord.reported_at.desc()).limit(200)).all()
    return [{"id": x.id, "person_id": x.person_id, "case_type": x.case_type, "summary": x.summary, "status": x.status, "resolution": x.resolution, "reported_at": x.reported_at} for x in items]

@router.post("/cases")
def create_case(data: CaseIn, db: Session = Depends(get_db), user: User = Depends(require("cases.create"))):
    item = CaseRecord(person_id=data.person_id, case_type=data.case_type, summary=data.summary, reported_by=user.id); db.add(item); db.flush()
    target = data.person_id or item.id; record_event(db, entity_type="PERSON" if data.person_id else "CASE", entity_id=target, event_type="CASE_REPORTED", actor_user_id=user.id, payload={"case_id": item.id, "case_type": data.case_type})
    db.commit(); return {"id": item.id, "status": item.status}

@router.post("/cases/{case_id}/evidence")
def add_evidence(case_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require("cases.create"))):
    item = db.get(CaseRecord, case_id)
    if not item: raise HTTPException(404, "Caso no encontrado")
    content = file.file.read(); digest = hashlib.sha256(content).hexdigest(); folder = load_settings().data_dir / "evidence" / case_id; folder.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "evidence.bin").name; path = folder / f"{digest[:12]}-{safe_name}"; path.write_bytes(content)
    ev = Evidence(case_id=case_id, original_name=safe_name, stored_path=str(path), sha256=digest, mime_type=file.content_type, uploaded_by=user.id); db.add(ev); db.commit(); return {"id": ev.id, "sha256": digest}

@router.post("/cases/{case_id}/resolve")
def resolve_case(case_id: str, data: CaseResolveIn, db: Session = Depends(get_db), user: User = Depends(require("cases.resolve"))):
    item = db.get(CaseRecord, case_id)
    if not item: raise HTTPException(404, "Caso no encontrado")
    item.status = "RESOLVED"; item.resolution = data.resolution; item.resolved_by = user.id; item.resolved_at = datetime.now(timezone.utc)
    record_event(db, entity_type="PERSON" if item.person_id else "CASE", entity_id=item.person_id or item.id, event_type="CASE_RESOLVED", actor_user_id=user.id, payload={"case_id": item.id, "resolution": data.resolution}); db.commit(); return {"id": item.id, "status": item.status}

@router.post("/imports/{kind}/preview")
def import_preview(kind: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require("attendance.import"))):
    if kind not in {"attendance", "personnel"}: raise HTTPException(422, "Tipo de importación no soportado")
    try:
        batch = preview_import(db, kind=kind, filename=file.filename or "upload.xlsx", content=file.file.read(), user_id=user.id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"batch_id": batch.id, "status": batch.status, "sha256": batch.sha256, "summary": batch.summary}

@router.post("/imports/{batch_id}/commit")
def import_commit(batch_id: str, db: Session = Depends(get_db), user: User = Depends(require("imports.commit"))):
    batch = db.get(ImportBatch, batch_id)
    if not batch: raise HTTPException(404, "Lote no encontrado")
    try: result = commit_import(db, batch, user.id)
    except ValueError as e: raise HTTPException(409, str(e))
    return result

@router.get("/imports/{batch_id}/issues")
def import_issues(batch_id: str, db: Session = Depends(get_db), user: User = Depends(require("attendance.import"))):
    items = db.scalars(select(ImportIssue).where(ImportIssue.batch_id == batch_id).order_by(ImportIssue.row_number)).all()
    return [{"id": x.id, "row_number": x.row_number, "issue_type": x.issue_type, "message": x.message, "status": x.status} for x in items]

@router.post("/projects")
def create_project(data: ProjectIn, db: Session = Depends(get_db), user: User = Depends(require("projects.manage"))):
    p = Project(code=data.code.strip().upper(), name=data.name.strip(), start_date=data.start_date); db.add(p); db.commit(); db.refresh(p); return {"id": p.id}

@router.get("/projects")
def projects(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [{"id": p.id, "code": p.code, "name": p.name, "status": p.status} for p in db.scalars(select(Project).order_by(Project.name)).all()]

@router.post("/groups")
def create_group(data: GroupIn, db: Session = Depends(get_db), user: User = Depends(require("projects.manage"))):
    g = WorkGroup(code=data.code.strip().upper(), name=data.name.strip(), project_id=data.project_id); db.add(g); db.commit(); db.refresh(g); return {"id": g.id}

@router.get("/audit")
def audit_log(db: Session = Depends(get_db), user: User = Depends(require("audit.view"))):
    items = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)).all()
    return [{"id": x.id, "action": x.action, "entity_type": x.entity_type, "entity_id": x.entity_id, "user_id": x.user_id, "created_at": x.created_at} for x in items]

# ===========================================================================
# Alpha.3: perfiles configurables, RRHH operativo, Asset Core, Tracking Nodes,
# taller, inventario y evidencias. Las reglas que pueden variar por operación
# se consultan desde catálogo; no se asume que un código sembrado sea eterno.
# ===========================================================================

PROTECTED_BASE_ROLES = {"ADMIN", "OFFICE", "HR", "HSE", "SUPERVISOR", "MATERIAL", "TALLER"}


def _code(value: str) -> str:
    return re.sub(r"[^A-Z0-9_.-]+", "_", value.strip().upper()).strip("_")


def _catalog_item(db: Session, catalog: str, code: str, required: bool = True) -> CatalogItem | None:
    item = db.scalar(select(CatalogItem).where(
        CatalogItem.catalog == _code(catalog), CatalogItem.code == _code(code), CatalogItem.active.is_(True)
    ))
    if required and not item:
        raise HTTPException(422, f"Código no válido/activo para {catalog}: {code}")
    return item


def _asset_type(db: Session, code: str) -> AssetType:
    item = db.scalar(select(AssetType).where(AssetType.code == _code(code), AssetType.active.is_(True)))
    if not item:
        raise HTTPException(422, f"Tipo de activo no válido/activo: {code}")
    return item


def _asset_technology(db: Session, code: str | None) -> AssetTechnology | None:
    if not code:
        return None
    item = db.scalar(select(AssetTechnology).where(AssetTechnology.code == _code(code), AssetTechnology.active.is_(True)))
    if not item:
        raise HTTPException(422, f"Tecnología no válida/activa: {code}")
    return item


def _asset_label(db: Session, asset: Asset) -> str:
    if asset.internal_code:
        return asset.internal_code
    if asset.serial_number:
        return asset.serial_number
    ident = db.scalar(select(AssetIdentifier).where(AssetIdentifier.asset_id == asset.id).order_by(AssetIdentifier.is_primary.desc()))
    return ident.value if ident else asset.id


def _apply_asset_movement(db: Session, asset: Asset, data: AssetMoveIn, actor_user_id: str | None) -> AssetMovement:
    movement = _catalog_item(db, "ASSET_MOVEMENT", data.movement_type)
    atype = db.get(AssetType, asset.asset_type_id)
    required_cap = (movement.metadata_json or {}).get("requires_capability")
    if required_cap and (not atype or required_cap not in (atype.capabilities or [])):
        raise HTTPException(422, f"El tipo de activo no declara la capacidad requerida: {required_cap}")

    status_after = _code(data.status_after) if data.status_after else (movement.metadata_json or {}).get("status_after")
    if status_after:
        _catalog_item(db, "ASSET_STATUS", status_after)

    # La custodia actual es un snapshot para consultas rápidas; el historial
    # autoritativo queda en AssetCustody y AssetMovement.
    if (movement.metadata_json or {}).get("opens_custody"):
        open_rows = db.scalars(select(AssetCustody).where(AssetCustody.asset_id == asset.id, AssetCustody.end_at.is_(None))).all()
        for row in open_rows:
            row.end_at = data.occurred_at or datetime.now(timezone.utc)
        custody = AssetCustody(
            asset_id=asset.id, person_id=data.responsible_person_id, project_id=data.project_id,
            group_id=data.group_id, location_id=data.location_id, start_at=data.occurred_at or datetime.now(timezone.utc),
            assigned_by=actor_user_id, note=data.note,
        )
        db.add(custody)
        asset.custodian_person_id = data.responsible_person_id
    elif (movement.metadata_json or {}).get("closes_custody"):
        open_rows = db.scalars(select(AssetCustody).where(AssetCustody.asset_id == asset.id, AssetCustody.end_at.is_(None))).all()
        for row in open_rows:
            row.end_at = data.occurred_at or datetime.now(timezone.utc)
        asset.custodian_person_id = None

    if status_after:
        asset.status_code = status_after
    if data.project_id is not None:
        asset.current_project_id = data.project_id
    if data.group_id is not None:
        asset.current_group_id = data.group_id
    if data.location_id is not None:
        asset.current_location_id = data.location_id
    if data.responsible_person_id is not None and not (movement.metadata_json or {}).get("closes_custody"):
        asset.custodian_person_id = data.responsible_person_id

    row = AssetMovement(
        asset_id=asset.id, movement_type=movement.code, status_after=status_after,
        project_id=data.project_id, group_id=data.group_id, location_id=data.location_id,
        responsible_person_id=data.responsible_person_id, line_code=data.line_code, stake_code=data.stake_code,
        occurred_at=data.occurred_at or datetime.now(timezone.utc), actor_user_id=actor_user_id,
        source_type=data.source_type, source_id=data.source_id,
        participant_person_ids=data.participant_person_ids, note=data.note, metadata_json=data.metadata,
    )
    db.add(row)
    record_event(
        db, entity_type="ASSET", entity_id=asset.id, event_type=movement.code,
        occurred_at=row.occurred_at, project_id=data.project_id, source_type=data.source_type,
        source_id=data.source_id, actor_user_id=actor_user_id,
        payload={"status_after": status_after, "line": data.line_code, "stake": data.stake_code,
                 "responsible_person_id": data.responsible_person_id, **(data.metadata or {})},
    )
    return row


@router.get("/permissions")
def permissions(db: Session = Depends(get_db), user: User = Depends(require("roles.manage"))):
    return [{"code": p.code, "description": p.description} for p in db.scalars(select(Permission).order_by(Permission.code)).all()]


@router.post("/roles")
def create_role(data: RoleCreateIn, db: Session = Depends(get_db), user: User = Depends(require("roles.manage"))):
    name = _code(data.name)
    if not name:
        raise HTTPException(422, "Nombre de rol inválido")
    if db.scalar(select(Role).where(Role.name == name)):
        raise HTTPException(409, "El rol ya existe")
    perms = db.scalars(select(Permission).where(Permission.code.in_(data.permissions))).all()
    if len(perms) != len(set(data.permissions)):
        raise HTTPException(422, "Uno o más permisos no existen")
    role = Role(name=name, description=data.description.strip(), permissions=list(perms))
    db.add(role); db.commit(); db.refresh(role)
    audit(db, user_id=user.id, action="ROLE_CREATE", entity_type="ROLE", entity_id=role.id, after={"name": name, "permissions": data.permissions})
    db.commit()
    return {"id": role.id, "name": role.name, "permissions": sorted(p.code for p in role.permissions)}


@router.put("/roles/{role_name}")
def update_role(role_name: str, data: RoleCreateIn, db: Session = Depends(get_db), user: User = Depends(require("roles.manage"))):
    name = _code(role_name)
    if name in PROTECTED_BASE_ROLES:
        raise HTTPException(409, "Los perfiles base están protegidos; cree o edite un perfil personalizado")
    role = db.scalar(select(Role).where(Role.name == name))
    if not role:
        raise HTTPException(404, "Rol no encontrado")
    perms = db.scalars(select(Permission).where(Permission.code.in_(data.permissions))).all()
    if len(perms) != len(set(data.permissions)):
        raise HTTPException(422, "Uno o más permisos no existen")
    role.description = data.description.strip(); role.permissions = list(perms)
    db.commit()
    return {"id": role.id, "name": role.name, "permissions": sorted(p.code for p in role.permissions)}


@router.put("/users/{user_id}/roles")
def update_user_roles(user_id: str, data: UserRolesIn, db: Session = Depends(get_db), user: User = Depends(require("users.manage"))):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Usuario no encontrado")
    names = {_code(x) for x in data.roles}
    roles = db.scalars(select(Role).where(Role.name.in_(names))).all()
    if len(roles) != len(names):
        raise HTTPException(422, "Uno o más roles no existen")
    had_admin = any(r.name == "ADMIN" for r in target.roles)
    if had_admin and "ADMIN" not in names:
        admins = [u for u in db.scalars(select(User).where(User.active.is_(True))).all() if any(r.name == "ADMIN" for r in u.roles)]
        if len(admins) <= 1:
            raise HTTPException(409, "No se puede retirar ADMIN al último administrador activo")
    target.roles = list(roles); db.commit()
    return {"id": target.id, "roles": sorted(r.name for r in target.roles)}


@router.get("/catalogs")
def catalog_names(db: Session = Depends(get_db), user: User = Depends(current_user)):
    names = db.scalars(select(CatalogItem.catalog).distinct().order_by(CatalogItem.catalog)).all()
    return list(names)


@router.get("/catalogs/{catalog}")
def catalog_items(catalog: str, include_inactive: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(CatalogItem).where(CatalogItem.catalog == _code(catalog))
    if not include_inactive:
        stmt = stmt.where(CatalogItem.active.is_(True))
    rows = db.scalars(stmt.order_by(CatalogItem.sort_order, CatalogItem.name)).all()
    return [{"id": x.id, "code": x.code, "name": x.name, "description": x.description, "active": x.active,
             "sort_order": x.sort_order, "metadata": x.metadata_json} for x in rows]


@router.post("/catalogs/{catalog}")
def create_catalog_item(catalog: str, data: CatalogItemIn, db: Session = Depends(get_db), user: User = Depends(require("catalogs.manage"))):
    cat, code = _code(catalog), _code(data.code)
    if db.scalar(select(CatalogItem).where(CatalogItem.catalog == cat, CatalogItem.code == code)):
        raise HTTPException(409, "Código ya existe en el catálogo")
    row = CatalogItem(catalog=cat, code=code, name=data.name.strip(), description=data.description,
                      active=data.active, sort_order=data.sort_order, metadata_json=data.metadata)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "catalog": row.catalog, "code": row.code, "name": row.name}


@router.put("/catalogs/{catalog}/{code}")
def update_catalog_item(catalog: str, code: str, data: CatalogItemIn, db: Session = Depends(get_db), user: User = Depends(require("catalogs.manage"))):
    row = db.scalar(select(CatalogItem).where(CatalogItem.catalog == _code(catalog), CatalogItem.code == _code(code)))
    if not row: raise HTTPException(404, "Elemento de catálogo no encontrado")
    row.name = data.name.strip(); row.description = data.description; row.active = data.active
    row.sort_order = data.sort_order; row.metadata_json = data.metadata
    db.commit(); return {"id": row.id, "code": row.code, "active": row.active}


@router.get("/organizations")
def organizations(db: Session = Depends(get_db), user: User = Depends(require("person.view"))):
    return [{"id": x.id, "code": x.code, "name": x.name, "organization_type": x.organization_type, "active": x.active}
            for x in db.scalars(select(Organization).order_by(Organization.name)).all()]


@router.post("/organizations")
def create_organization(data: OrganizationIn, db: Session = Depends(get_db), user: User = Depends(require("organizations.manage"))):
    _catalog_item(db, "ORGANIZATION_TYPE", data.organization_type)
    row = Organization(code=_code(data.code), name=data.name.strip(), organization_type=_code(data.organization_type), metadata_json=data.metadata)
    db.add(row); db.commit(); db.refresh(row); return {"id": row.id, "code": row.code}


@router.get("/locations")
def locations(project_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Location).where(Location.active.is_(True))
    if project_id: stmt = stmt.where(or_(Location.project_id == project_id, Location.project_id.is_(None)))
    rows = db.scalars(stmt.order_by(Location.name)).all()
    return [{"id": x.id, "code": x.code, "name": x.name, "location_type": x.location_type,
             "project_id": x.project_id, "parent_id": x.parent_id, "metadata": x.metadata_json} for x in rows]


@router.post("/locations")
def create_location(data: LocationIn, db: Session = Depends(get_db), user: User = Depends(require("locations.manage"))):
    _catalog_item(db, "LOCATION_TYPE", data.location_type)
    row = Location(code=_code(data.code), name=data.name.strip(), location_type=_code(data.location_type),
                   project_id=data.project_id, parent_id=data.parent_id, metadata_json=data.metadata)
    db.add(row); db.commit(); db.refresh(row); return {"id": row.id, "code": row.code}


@router.get("/persons/{person_id}/hr-profile")
def get_hr_profile(person_id: str, db: Session = Depends(get_db), user: User = Depends(require("person.view"))):
    if not db.get(Person, person_id): raise HTTPException(404, "Persona no encontrada")
    p = db.get(PersonHRProfile, person_id)
    return None if not p else {"person_id": p.person_id, "category": p.category, "license_number": p.license_number,
        "license_type": p.license_type, "license_expiry": p.license_expiry, "rotation_on_days": p.rotation_on_days,
        "rotation_off_days": p.rotation_off_days, "phone": p.phone, "emergency_contact": p.emergency_contact,
        "metadata": p.metadata_json}


@router.put("/persons/{person_id}/hr-profile")
def put_hr_profile(person_id: str, data: HRProfileIn, db: Session = Depends(get_db), user: User = Depends(require("person.edit"))):
    if not db.get(Person, person_id): raise HTTPException(404, "Persona no encontrada")
    row = db.get(PersonHRProfile, person_id) or PersonHRProfile(person_id=person_id)
    for key in ("category", "license_number", "license_type", "license_expiry", "rotation_on_days", "rotation_off_days", "phone", "emergency_contact"):
        setattr(row, key, getattr(data, key))
    row.metadata_json = data.metadata
    db.add(row)
    record_event(db, entity_type="PERSON", entity_id=person_id, event_type="HR_PROFILE_UPDATED", actor_user_id=user.id,
                 payload={"category": data.category, "license_type": data.license_type, "license_expiry": data.license_expiry.isoformat() if data.license_expiry else None,
                          "rotation": [data.rotation_on_days, data.rotation_off_days]})
    db.commit(); return {"person_id": person_id, "ok": True}


@router.post("/persons/{person_id}/assignments")
def assign_person(person_id: str, data: PersonAssignmentIn, db: Session = Depends(get_db), user: User = Depends(require("person.edit"))):
    if not db.get(Person, person_id): raise HTTPException(404, "Persona no encontrada")
    when = data.start_at or datetime.now(timezone.utc)
    for current in db.scalars(select(PersonAssignment).where(PersonAssignment.person_id == person_id, PersonAssignment.end_at.is_(None))).all():
        current.end_at = when
    # Mantener compatibilidad con el módulo alpha.2 de grupos.
    for current in db.scalars(select(GroupAssignment).where(GroupAssignment.person_id == person_id, GroupAssignment.end_date.is_(None))).all():
        current.end_date = when.date()
    if data.group_id:
        db.add(GroupAssignment(person_id=person_id, group_id=data.group_id, start_date=when.date()))
    row = PersonAssignment(person_id=person_id, project_id=data.project_id, group_id=data.group_id,
                           location_id=data.location_id, supervisor_person_id=data.supervisor_person_id,
                           unit_asset_id=data.unit_asset_id, role_name=data.role_name, start_at=when, metadata_json=data.metadata)
    db.add(row); db.flush()
    record_event(db, entity_type="PERSON", entity_id=person_id, event_type="OPERATIONAL_ASSIGNMENT",
                 occurred_at=when, project_id=data.project_id, actor_user_id=user.id,
                 payload={"group_id": data.group_id, "location_id": data.location_id, "supervisor_person_id": data.supervisor_person_id,
                          "unit_asset_id": data.unit_asset_id, "role_name": data.role_name})
    db.commit(); return {"id": row.id}


@router.get("/persons/{person_id}/assignments")
def person_assignments(person_id: str, db: Session = Depends(get_db), user: User = Depends(require("person.view"))):
    rows = db.scalars(select(PersonAssignment).where(PersonAssignment.person_id == person_id).order_by(PersonAssignment.start_at.desc())).all()
    return [{"id": x.id, "project_id": x.project_id, "group_id": x.group_id, "location_id": x.location_id,
             "supervisor_person_id": x.supervisor_person_id, "unit_asset_id": x.unit_asset_id, "role_name": x.role_name,
             "start_at": x.start_at, "end_at": x.end_at, "metadata": x.metadata_json} for x in rows]


@router.post("/attendance")
def record_attendance(data: AttendanceIn, db: Session = Depends(get_db), user: User = Depends(require("attendance.manage"))):
    _catalog_item(db, "ATTENDANCE_STATUS", data.status)
    if not db.get(Person, data.person_id): raise HTTPException(404, "Persona no encontrada")
    row = db.scalar(select(AttendanceRecord).where(AttendanceRecord.person_id == data.person_id, AttendanceRecord.attendance_date == data.attendance_date))
    if row:
        row.status = _code(data.status)
    else:
        row = AttendanceRecord(person_id=data.person_id, attendance_date=data.attendance_date, status=_code(data.status)); db.add(row)
    record_event(db, entity_type="PERSON", entity_id=data.person_id, event_type="ATTENDANCE_RECORDED",
                 occurred_at=datetime.combine(data.attendance_date, datetime.min.time(), tzinfo=timezone.utc), actor_user_id=user.id,
                 payload={"status": _code(data.status)})
    db.commit(); return {"id": row.id, "status": row.status}


@router.post("/engagements/{engagement_id}/lifecycle")
def employment_lifecycle(engagement_id: str, data: LifecycleEventIn, db: Session = Depends(get_db), user: User = Depends(require("person.edit"))):
    eng = db.get(EmploymentEngagement, engagement_id)
    if not eng: raise HTTPException(404, "Relación laboral no encontrada")
    cfg = _catalog_item(db, "EMPLOYMENT_EVENT", data.event_type)
    row = EmploymentLifecycleEvent(engagement_id=engagement_id, event_type=cfg.code, occurred_on=data.occurred_on,
                                   reason=data.reason, actor_user_id=user.id, metadata_json=data.metadata)
    db.add(row)
    if (cfg.metadata_json or {}).get("closes_engagement"):
        if data.occurred_on < eng.start_date: raise HTTPException(422, "La fecha del evento no puede ser anterior al alta")
        eng.end_date = data.occurred_on; eng.status = (cfg.metadata_json or {}).get("final_status", "ENDED")
        person = db.get(Person, eng.person_id)
        remaining = db.scalar(select(EmploymentEngagement).where(EmploymentEngagement.person_id == eng.person_id,
                                                                  EmploymentEngagement.id != eng.id, EmploymentEngagement.end_date.is_(None)))
        if person and not remaining: person.active = False
    record_event(db, entity_type="PERSON", entity_id=eng.person_id, event_type=f"EMPLOYMENT_{cfg.code}",
                 occurred_at=datetime.combine(data.occurred_on, datetime.min.time(), tzinfo=timezone.utc),
                 project_id=eng.project_id, actor_user_id=user.id, payload={"engagement_id": eng.id, "reason": data.reason, **data.metadata})
    db.commit(); return {"id": row.id, "engagement_status": eng.status, "end_date": eng.end_date}


@router.get("/asset-types")
def asset_types(db: Session = Depends(get_db), user: User = Depends(require("assets.view"))):
    return [{"id": x.id, "code": x.code, "name": x.name, "active": x.active, "capabilities": x.capabilities, "metadata": x.metadata_json}
            for x in db.scalars(select(AssetType).order_by(AssetType.name)).all()]


@router.post("/asset-types")
def create_asset_type(data: AssetTypeIn, db: Session = Depends(get_db), user: User = Depends(require("catalogs.manage"))):
    row = AssetType(code=_code(data.code), name=data.name.strip(), capabilities=sorted(set(_code(x).lower() for x in data.capabilities)), metadata_json=data.metadata)
    db.add(row); db.commit(); db.refresh(row); return {"id": row.id, "code": row.code}


@router.put("/asset-types/{code}")
def update_asset_type(code: str, data: AssetTypeIn, db: Session = Depends(get_db), user: User = Depends(require("catalogs.manage"))):
    row = db.scalar(select(AssetType).where(AssetType.code == _code(code)))
    if not row: raise HTTPException(404, "Tipo de activo no encontrado")
    row.name=data.name.strip(); row.capabilities=sorted(set(_code(x).lower() for x in data.capabilities)); row.metadata_json=data.metadata
    db.commit(); return {"id": row.id, "code": row.code, "capabilities": row.capabilities}


@router.get("/asset-technologies")
def asset_technologies(db: Session = Depends(get_db), user: User = Depends(require("assets.view"))):
    return [{"id": x.id, "code": x.code, "name": x.name, "vendor": x.vendor, "active": x.active, "metadata": x.metadata_json}
            for x in db.scalars(select(AssetTechnology).order_by(AssetTechnology.name)).all()]


@router.post("/asset-technologies")
def create_asset_technology(data: AssetTechnologyIn, db: Session = Depends(get_db), user: User = Depends(require("catalogs.manage"))):
    row=AssetTechnology(code=_code(data.code), name=data.name.strip(), vendor=data.vendor, metadata_json=data.metadata)
    db.add(row); db.commit(); db.refresh(row); return {"id": row.id, "code": row.code}


@router.post("/assets/bulk/preview")
def asset_bulk_preview(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require("assets.bulk"))):
    content=file.file.read()
    try: text=content.decode("utf-8-sig")
    except UnicodeDecodeError: raise HTTPException(422, "CSV debe estar en UTF-8")
    reader=csv.DictReader(io.StringIO(text))
    rows=[]; issues=[]
    for n, raw in enumerate(reader, start=2):
        norm={(_code(k) if k else ""): (v.strip() if isinstance(v,str) else v) for k,v in raw.items()}
        type_code=norm.get("TYPE") or norm.get("TIPO")
        tech=norm.get("TECHNOLOGY") or norm.get("TECNOLOGIA")
        status=norm.get("STATUS") or norm.get("ESTADO") or "AVAILABLE"
        if not type_code or not db.scalar(select(AssetType).where(AssetType.code==_code(type_code),AssetType.active.is_(True))):
            issues.append({"row":n,"message":f"Tipo inexistente/inactivo: {type_code}"})
        if tech and not db.scalar(select(AssetTechnology).where(AssetTechnology.code==_code(tech),AssetTechnology.active.is_(True))):
            issues.append({"row":n,"message":f"Tecnología inexistente/inactiva: {tech}"})
        if not db.scalar(select(CatalogItem).where(CatalogItem.catalog=="ASSET_STATUS",CatalogItem.code==_code(status),CatalogItem.active.is_(True))):
            issues.append({"row":n,"message":f"Estado inexistente/inactivo: {status}"})
        rows.append(norm)
    folder=load_settings().data_dir/"imports"/"assets"; folder.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(content).hexdigest(); path=folder/f"{digest}.csv"; path.write_bytes(content)
    batch=ImportBatch(kind="assets",original_name=Path(file.filename or "assets.csv").name,stored_path=str(path),sha256=digest,
                      status="PREVIEW",summary={"rows":len(rows),"issues":issues,"parsed":rows},created_by=user.id)
    db.add(batch); db.commit(); db.refresh(batch)
    return {"batch_id":batch.id,"rows":len(rows),"issues":issues,"can_commit":not issues}


@router.post("/assets/bulk/{batch_id}/commit")
def asset_bulk_commit(batch_id: str, db: Session = Depends(get_db), user: User = Depends(require("assets.bulk"))):
    batch=db.get(ImportBatch,batch_id)
    if not batch or batch.kind!="assets": raise HTTPException(404,"Lote de activos no encontrado")
    if batch.status!="PREVIEW": raise HTTPException(409,"El lote ya fue procesado")
    parsed=(batch.summary or {}).get("parsed",[]); issues=(batch.summary or {}).get("issues",[])
    if issues: raise HTTPException(409,"El lote contiene incidencias; corrija antes de confirmar")
    created=[]
    known={"TYPE","TIPO","TECHNOLOGY","TECNOLOGIA","INTERNAL_CODE","CODIGO","CODIGO_INTERNO","SERIAL","SERIE","NUMERO_SERIE","STATUS","ESTADO","IMEI","QR","ECONOMIC_NUMBER","NUMERO_ECONOMICO","IDENTIFIER_KIND","IDENTIFICADOR_TIPO","IDENTIFIER_VALUE","IDENTIFICADOR"}
    for raw in parsed:
        t=_asset_type(db,raw.get("TYPE") or raw.get("TIPO")); tech=_asset_technology(db,raw.get("TECHNOLOGY") or raw.get("TECNOLOGIA"))
        status=_code(raw.get("STATUS") or raw.get("ESTADO") or "AVAILABLE"); _catalog_item(db,"ASSET_STATUS",status)
        metadata={k:v for k,v in raw.items() if k not in known and v not in (None,"")}
        asset=Asset(asset_type_id=t.id,technology_id=tech.id if tech else None,
                    internal_code=raw.get("INTERNAL_CODE") or raw.get("CODIGO_INTERNO") or raw.get("CODIGO") or None,
                    serial_number=raw.get("SERIAL") or raw.get("SERIE") or raw.get("NUMERO_SERIE") or None,
                    status_code=status,metadata_json=metadata)
        db.add(asset);db.flush()
        idents=[]
        for kind,value in (("IMEI",raw.get("IMEI")),("QR",raw.get("QR")),("ECONOMIC_NUMBER",raw.get("ECONOMIC_NUMBER") or raw.get("NUMERO_ECONOMICO")),
                           (raw.get("IDENTIFIER_KIND") or raw.get("IDENTIFICADOR_TIPO"),raw.get("IDENTIFIER_VALUE") or raw.get("IDENTIFICADOR"))):
            if kind and value: idents.append(AssetIdentifier(asset_id=asset.id,kind=_code(kind),value=value,is_primary=False))
        db.add_all(idents)
        _apply_asset_movement(db,asset,AssetMoveIn(movement_type="REGISTER",status_after=status,source_type="IMPORT",source_id=batch.id,metadata={"original_name":batch.original_name}),user.id)
        created.append(asset.id)
    batch.status="COMMITTED";batch.committed_at=datetime.now(timezone.utc);db.commit()
    return {"batch_id":batch.id,"created":len(created),"asset_ids":created}


@router.post("/assets")
def create_asset(data: AssetIn, db: Session = Depends(get_db), user: User = Depends(require("assets.create"))):
    t=_asset_type(db,data.type_code); tech=_asset_technology(db,data.technology_code); status=_code(data.status_code); _catalog_item(db,"ASSET_STATUS",status)
    if data.internal_code and db.scalar(select(Asset).where(Asset.internal_code==data.internal_code.strip())):
        raise HTTPException(409,"Código interno ya existe")
    asset=Asset(asset_type_id=t.id,technology_id=tech.id if tech else None,internal_code=data.internal_code.strip() if data.internal_code else None,
                serial_number=data.serial_number.strip() if data.serial_number else None,status_code=status,condition_code=_code(data.condition_code) if data.condition_code else None,
                current_project_id=data.project_id,current_group_id=data.group_id,current_location_id=data.location_id,custodian_person_id=data.custodian_person_id,
                notes=data.notes,metadata_json=data.metadata)
    db.add(asset);db.flush()
    for ident in data.identifiers:
        db.add(AssetIdentifier(asset_id=asset.id,kind=_code(ident.kind),value=ident.value.strip(),is_primary=ident.is_primary))
    _apply_asset_movement(db,asset,AssetMoveIn(movement_type="REGISTER",status_after=status,project_id=data.project_id,group_id=data.group_id,
                                               location_id=data.location_id,responsible_person_id=data.custodian_person_id,note="Alta de activo"),user.id)
    audit(db,user_id=user.id,action="ASSET_CREATE",entity_type="ASSET",entity_id=asset.id,after=data.model_dump(mode="json"));db.commit()
    return {"id":asset.id,"label":_asset_label(db,asset)}


@router.get("/assets")
def list_assets(q: str="", status: str|None=None, type_code: str|None=None, db: Session=Depends(get_db), user:User=Depends(require("assets.view"))):
    stmt=select(Asset).where(Asset.active.is_(True))
    if status: stmt=stmt.where(Asset.status_code==_code(status))
    if type_code:
        t=db.scalar(select(AssetType).where(AssetType.code==_code(type_code)))
        stmt=stmt.where(Asset.asset_type_id==(t.id if t else "__none__"))
    if q.strip():
        term=f"%{q.strip()}%"; ids=select(AssetIdentifier.asset_id).where(AssetIdentifier.value.ilike(term))
        stmt=stmt.where(or_(Asset.internal_code.ilike(term),Asset.serial_number.ilike(term),Asset.id.in_(ids)))
    rows=db.scalars(stmt.order_by(Asset.updated_at.desc()).limit(300)).all()
    out=[]
    for a in rows:
        t=db.get(AssetType,a.asset_type_id);tech=db.get(AssetTechnology,a.technology_id) if a.technology_id else None
        out.append({"id":a.id,"label":_asset_label(db,a),"type_code":t.code if t else None,"type_name":t.name if t else None,
                    "technology":tech.code if tech else None,"internal_code":a.internal_code,"serial_number":a.serial_number,"status_code":a.status_code,
                    "project_id":a.current_project_id,"group_id":a.current_group_id,"location_id":a.current_location_id,"custodian_person_id":a.custodian_person_id})
    return out


@router.get("/assets/{asset_id}")
def asset_detail(asset_id:str, db:Session=Depends(get_db), user:User=Depends(require("assets.view"))):
    a=db.get(Asset,asset_id)
    if not a: raise HTTPException(404,"Activo no encontrado")
    t=db.get(AssetType,a.asset_type_id);tech=db.get(AssetTechnology,a.technology_id) if a.technology_id else None
    ids=db.scalars(select(AssetIdentifier).where(AssetIdentifier.asset_id==asset_id).order_by(AssetIdentifier.is_primary.desc(),AssetIdentifier.kind)).all()
    moves=db.scalars(select(AssetMovement).where(AssetMovement.asset_id==asset_id).order_by(AssetMovement.occurred_at.desc()).limit(200)).all()
    maint=db.scalars(select(MaintenanceOrder).where(MaintenanceOrder.asset_id==asset_id).order_by(MaintenanceOrder.opened_at.desc()).limit(50)).all()
    health=db.scalars(select(AssetHealthObservation).where(AssetHealthObservation.asset_id==asset_id).order_by(AssetHealthObservation.observed_at.desc()).limit(50)).all()
    evs=db.scalars(select(EvidenceRecord).where(EvidenceRecord.entity_type=="ASSET",EvidenceRecord.entity_id==asset_id).order_by(EvidenceRecord.created_at.desc())).all()
    return {"asset":{"id":a.id,"label":_asset_label(db,a),"type_code":t.code if t else None,"type_name":t.name if t else None,
                     "capabilities":t.capabilities if t else [],"technology":tech.code if tech else None,"internal_code":a.internal_code,
                     "serial_number":a.serial_number,"status_code":a.status_code,"condition_code":a.condition_code,"project_id":a.current_project_id,
                     "group_id":a.current_group_id,"location_id":a.current_location_id,"custodian_person_id":a.custodian_person_id,"notes":a.notes,"metadata":a.metadata_json},
            "identifiers":[{"kind":x.kind,"value":x.value,"is_primary":x.is_primary} for x in ids],
            "movements":[{"id":x.id,"movement_type":x.movement_type,"status_after":x.status_after,"project_id":x.project_id,"group_id":x.group_id,
                          "location_id":x.location_id,"responsible_person_id":x.responsible_person_id,"line_code":x.line_code,"stake_code":x.stake_code,
                          "occurred_at":x.occurred_at,"recorded_at":x.recorded_at,"participants":x.participant_person_ids,"note":x.note,"metadata":x.metadata_json} for x in moves],
            "maintenance":[{"id":x.id,"status":x.status,"priority":x.priority,"symptom":x.symptom,"diagnosis":x.diagnosis,"action_taken":x.action_taken,
                            "result":x.result,"opened_at":x.opened_at,"closed_at":x.closed_at,"downtime_minutes":x.downtime_minutes} for x in maint],
            "health":[{"id":x.id,"observed_at":x.observed_at,"source":x.source,"soh_percent":x.soh_percent,"rul_days":x.rul_days,"health_score":x.health_score,
                       "confidence":x.confidence,"cycles":x.cycles,"operating_hours":x.operating_hours,"payload":x.payload} for x in health],
            "evidence":[{"id":x.id,"original_name":x.original_name,"relative_path":x.relative_path,"sha256":x.sha256,"created_at":x.created_at} for x in evs]}


@router.post("/assets/{asset_id}/movements")
def move_asset(asset_id:str,data:AssetMoveIn,db:Session=Depends(get_db),user:User=Depends(require("assets.move"))):
    a=db.get(Asset,asset_id)
    if not a: raise HTTPException(404,"Activo no encontrado")
    row=_apply_asset_movement(db,a,data,user.id);db.flush()
    audit(db,user_id=user.id,action="ASSET_MOVE",entity_type="ASSET",entity_id=a.id,after=data.model_dump(mode="json"));db.commit()
    return {"id":row.id,"status":a.status_code,"label":_asset_label(db,a)}


@router.post("/node-operations")
def create_node_operation(data:NodeOperationIn,db:Session=Depends(get_db),user:User=Depends(require("nodes.operate"))):
    op_cfg=_catalog_item(db,"NODE_OPERATION",data.operation_type)
    when=data.occurred_at or datetime.now(timezone.utc)
    op=NodeOperation(operation_type=op_cfg.code,project_id=data.project_id,group_id=data.group_id,location_id=data.location_id,line_code=data.line_code,
                     occurred_at=when,actor_user_id=user.id,participant_person_ids=data.participant_person_ids,source_type=data.source_type,source_id=data.source_id,
                     note=data.note,metadata_json=data.metadata)
    db.add(op);db.flush();processed=[]
    default_move=(op_cfg.metadata_json or {}).get("movement_type")
    for item in data.items:
        a=db.get(Asset,item.asset_id)
        if not a: raise HTTPException(404,f"Activo no encontrado: {item.asset_id}")
        t=db.get(AssetType,a.asset_type_id)
        if not t or "node_field" not in (t.capabilities or []): raise HTTPException(422,f"Activo {_asset_label(db,a)} no tiene capacidad node_field")
        result=_catalog_item(db,"NODE_RESULT",item.result_code,required=False) if item.result_code else None
        result_meta=(result.metadata_json or {}) if result else {}
        status_after=result_meta.get("status_after")
        # El catálogo NODE_RESULT puede declarar el movimiento que representa la excepción.
        # Si no lo declara, la operación de lote controla el movimiento; TRANSFER es último fallback.
        move_type=result_meta.get("movement_type") or default_move or (
            item.result_code if item.result_code and _catalog_item(db,"ASSET_MOVEMENT",item.result_code,required=False) else "TRANSFER"
        )
        previous=a.status_code
        move=_apply_asset_movement(db,a,AssetMoveIn(movement_type=move_type,status_after=status_after,project_id=data.project_id,group_id=data.group_id,
            location_id=data.location_id,responsible_person_id=item.responsible_person_id,line_code=data.line_code,stake_code=item.stake_to or item.stake_from,
            occurred_at=when,participant_person_ids=data.participant_person_ids,source_type=data.source_type,source_id=data.source_id,note=item.note,
            metadata={"node_operation_id":op.id,"result_code":item.result_code,"stake_from":item.stake_from,"stake_to":item.stake_to,**item.metadata}),user.id)
        oi=NodeOperationItem(operation_id=op.id,asset_id=a.id,stake_from=item.stake_from,stake_to=item.stake_to,result_code=_code(item.result_code) if item.result_code else None,
                             previous_status_code=previous,new_status_code=a.status_code,responsible_person_id=item.responsible_person_id,note=item.note,metadata_json=item.metadata)
        db.add(oi);processed.append({"asset_id":a.id,"movement_id":move.id,"from":previous,"to":a.status_code})
    db.commit();return {"id":op.id,"operation_type":op.operation_type,"items":processed}


@router.get("/node-operations")
def node_operations(asset_id:str|None=None,db:Session=Depends(get_db),user:User=Depends(require("nodes.view"))):
    stmt=select(NodeOperation).order_by(NodeOperation.occurred_at.desc()).limit(200)
    if asset_id:
        op_ids=select(NodeOperationItem.operation_id).where(NodeOperationItem.asset_id==asset_id);stmt=stmt.where(NodeOperation.id.in_(op_ids))
    rows=db.scalars(stmt).all();return [{"id":x.id,"operation_type":x.operation_type,"project_id":x.project_id,"group_id":x.group_id,"location_id":x.location_id,
        "line_code":x.line_code,"occurred_at":x.occurred_at,"participants":x.participant_person_ids,"source_type":x.source_type,"note":x.note,
        "item_count":db.scalar(select(func.count()).select_from(NodeOperationItem).where(NodeOperationItem.operation_id==x.id)) or 0} for x in rows]


@router.post("/maintenance")
def open_maintenance(data:MaintenanceOpenIn,db:Session=Depends(get_db),user:User=Depends(require("maintenance.manage"))):
    a=db.get(Asset,data.asset_id)
    if not a: raise HTTPException(404,"Activo no encontrado")
    t=db.get(AssetType,a.asset_type_id)
    if t and "maintenance" not in (t.capabilities or []): raise HTTPException(422,"El tipo de activo no declara capacidad maintenance")
    row=MaintenanceOrder(asset_id=a.id,priority=_code(data.priority),symptom=data.symptom,fault_code=data.fault_code,opened_by=user.id,metadata_json=data.metadata)
    db.add(row);db.flush();_apply_asset_movement(db,a,AssetMoveIn(movement_type="MAINTENANCE_IN",note=f"Orden {row.id}"),user.id);db.commit()
    return {"id":row.id,"status":row.status}


@router.get("/maintenance")
def list_maintenance(status:str|None=None,db:Session=Depends(get_db),user:User=Depends(require("maintenance.view"))):
    stmt=select(MaintenanceOrder)
    if status:stmt=stmt.where(MaintenanceOrder.status==_code(status))
    rows=db.scalars(stmt.order_by(MaintenanceOrder.opened_at.desc()).limit(200)).all()
    return [{"id":x.id,"asset_id":x.asset_id,"asset_label":_asset_label(db,db.get(Asset,x.asset_id)),"status":x.status,"priority":x.priority,"symptom":x.symptom,
             "fault_code":x.fault_code,"diagnosis":x.diagnosis,"action_taken":x.action_taken,"result":x.result,"opened_at":x.opened_at,"closed_at":x.closed_at,
             "downtime_minutes":x.downtime_minutes} for x in rows]


@router.put("/maintenance/{order_id}")
def update_maintenance(order_id:str,data:MaintenanceUpdateIn,db:Session=Depends(get_db),user:User=Depends(require("maintenance.manage"))):
    row=db.get(MaintenanceOrder,order_id)
    if not row:raise HTTPException(404,"Orden no encontrada")
    if data.status:_catalog_item(db,"MAINTENANCE_STATUS",data.status);row.status=_code(data.status)
    if data.diagnosis is not None:row.diagnosis=data.diagnosis
    if data.action_taken is not None:row.action_taken=data.action_taken
    if data.result is not None:row.result=data.result
    if data.downtime_minutes is not None:row.downtime_minutes=data.downtime_minutes
    row.metadata_json={**(row.metadata_json or {}),**data.metadata}
    if data.close:
        row.status="CLOSED";row.closed_at=datetime.now(timezone.utc);row.closed_by=user.id
        a=db.get(Asset,row.asset_id);_apply_asset_movement(db,a,AssetMoveIn(movement_type="MAINTENANCE_OUT",status_after=data.status_after or "AVAILABLE",note=f"Cierre orden {row.id}"),user.id)
    db.commit();return {"id":row.id,"status":row.status,"closed_at":row.closed_at}


@router.post("/maintenance/{order_id}/parts")
def add_maintenance_part(order_id:str,data:MaintenancePartIn,db:Session=Depends(get_db),user:User=Depends(require("maintenance.manage"))):
    if not db.get(MaintenanceOrder,order_id):raise HTTPException(404,"Orden no encontrada")
    row=MaintenancePart(maintenance_order_id=order_id,component_type=data.component_type,serial_removed=data.serial_removed,
                        serial_installed=data.serial_installed,quantity=data.quantity,note=data.note)
    db.add(row);db.commit();db.refresh(row);return {"id":row.id}


@router.post("/assets/{asset_id}/health")
def add_health(asset_id:str,data:HealthObservationIn,db:Session=Depends(get_db),user:User=Depends(require("maintenance.manage"))):
    a=db.get(Asset,asset_id)
    if not a:raise HTTPException(404,"Activo no encontrado")
    row=AssetHealthObservation(asset_id=a.id,observed_at=data.observed_at or datetime.now(timezone.utc),source=data.source,soh_percent=data.soh_percent,
                               rul_days=data.rul_days,health_score=data.health_score,confidence=data.confidence,cycles=data.cycles,operating_hours=data.operating_hours,
                               payload=data.payload,recorded_by=user.id)
    db.add(row)
    # IMPORTANTE: salud/RUL es observación/predicción. Nunca cambia por sí sola
    # el estado factual ni provoca una baja automática.
    record_event(db,entity_type="ASSET",entity_id=a.id,event_type="HEALTH_OBSERVED",occurred_at=row.observed_at,actor_user_id=user.id,
                 payload={"source":data.source,"soh_percent":data.soh_percent,"rul_days":data.rul_days,"health_score":data.health_score,"confidence":data.confidence})
    db.commit();return {"id":row.id,"asset_status_unchanged":a.status_code}


@router.post("/inventory/sessions")
def create_inventory_session(data:InventorySessionIn,db:Session=Depends(get_db),user:User=Depends(require("inventory.manage"))):
    row=InventorySession(name=data.name,project_id=data.project_id,location_id=data.location_id,created_by=user.id,notes=data.notes)
    db.add(row);db.commit();db.refresh(row);return {"id":row.id,"status":row.status}


@router.post("/inventory/sessions/{inventory_id}/count")
def inventory_count(inventory_id:str,data:InventoryCountIn,db:Session=Depends(get_db),user:User=Depends(require("inventory.manage"))):
    session=db.get(InventorySession,inventory_id)
    if not session or session.status!="OPEN":raise HTTPException(409,"Inventario no existe o ya está cerrado")
    a=db.get(Asset,data.asset_id)
    if not a:raise HTTPException(404,"Activo no encontrado")
    row=db.scalar(select(InventoryCount).where(InventoryCount.session_id==inventory_id,InventoryCount.asset_id==data.asset_id))
    if not row:row=InventoryCount(session_id=inventory_id,asset_id=a.id);db.add(row)
    row.found=data.found;row.observed_status_code=_code(data.observed_status_code) if data.observed_status_code else None;row.location_id=data.location_id;row.counted_by=user.id;row.counted_at=datetime.now(timezone.utc);row.note=data.note
    db.commit();return {"id":row.id,"found":row.found}


@router.post("/inventory/sessions/{inventory_id}/close")
def close_inventory(inventory_id:str,db:Session=Depends(get_db),user:User=Depends(require("inventory.closeout"))):
    session=db.get(InventorySession,inventory_id)
    if not session:raise HTTPException(404,"Inventario no encontrado")
    stmt=select(Asset).where(Asset.active.is_(True))
    if session.project_id:stmt=stmt.where(Asset.current_project_id==session.project_id)
    if session.location_id:stmt=stmt.where(Asset.current_location_id==session.location_id)
    expected=db.scalars(stmt).all();counts=db.scalars(select(InventoryCount).where(InventoryCount.session_id==inventory_id)).all();by_asset={x.asset_id:x for x in counts}
    missing=[a for a in expected if a.id not in by_asset or not by_asset[a.id].found]
    unexpected=[x for x in counts if x.asset_id not in {a.id for a in expected} and x.found]
    session.status="CLOSED";session.closed_at=datetime.now(timezone.utc);db.commit()
    return {"id":session.id,"expected":len(expected),"counted":len(counts),"missing":[{"asset_id":a.id,"label":_asset_label(db,a),"status":a.status_code} for a in missing],
            "unexpected":[{"asset_id":x.asset_id,"label":_asset_label(db,db.get(Asset,x.asset_id))} for x in unexpected]}


@router.get("/inventory/sessions/{inventory_id}")
def inventory_session_detail(inventory_id:str,db:Session=Depends(get_db),user:User=Depends(require("assets.view"))):
    s=db.get(InventorySession,inventory_id)
    if not s:raise HTTPException(404,"Inventario no encontrado")
    counts=db.scalars(select(InventoryCount).where(InventoryCount.session_id==inventory_id).order_by(InventoryCount.counted_at)).all()
    return {"id":s.id,"name":s.name,"status":s.status,"project_id":s.project_id,"location_id":s.location_id,"started_at":s.started_at,"closed_at":s.closed_at,
            "counts":[{"asset_id":x.asset_id,"label":_asset_label(db,db.get(Asset,x.asset_id)),"found":x.found,"observed_status_code":x.observed_status_code,"note":x.note} for x in counts]}


@router.get("/evidence/repositories")
def evidence_repositories(db:Session=Depends(get_db),user:User=Depends(require("evidence.view"))):
    return [{"id":x.id,"code":x.code,"name":x.name,"repository_type":x.repository_type,"mount_point":x.mount_point,"canonical_uri":x.canonical_uri,"active":x.active,"metadata":x.metadata_json}
            for x in db.scalars(select(EvidenceRepository).order_by(EvidenceRepository.name)).all()]


@router.post("/evidence/repositories")
def create_evidence_repository(data:EvidenceRepositoryIn,db:Session=Depends(get_db),user:User=Depends(require("evidence.manage"))):
    kind=_code(data.repository_type)
    if kind not in {"LOCAL","SMB"}:raise HTTPException(422,"repository_type debe ser LOCAL o SMB")
    row=EvidenceRepository(code=_code(data.code),name=data.name.strip(),repository_type=kind,mount_point=data.mount_point,
                           canonical_uri=data.canonical_uri,metadata_json=data.metadata)
    db.add(row);db.commit();db.refresh(row);return {"id":row.id,"code":row.code}


def _repository_root(repo:EvidenceRepository) -> Path:
    root=Path(repo.mount_point)
    if repo.repository_type=="SMB":
        # Fail-closed: si el NAS perdió el montaje no se escribe en una carpeta
        # local homónima, evitando una falsa sensación de respaldo remoto.
        if not root.exists() or not os.path.ismount(root):
            raise HTTPException(503,"Repositorio SMB/NAS no está montado; carga rechazada para proteger la evidencia")
    else:
        root.mkdir(parents=True,exist_ok=True)
    return root


def _safe_component(value:str) -> str:
    cleaned=re.sub(r"[^A-Za-z0-9._-]+","_",value.strip()).strip("._")
    return cleaned[:120] or "sin_nombre"


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
    """Calcula hash/tamaño en streaming para evidencias potencialmente grandes.

    Fotos, PDFs y videos de campo pueden superar con facilidad la memoria que
    conviene reservar a la Latitude.  Nunca usamos ``read_bytes()`` para estos
    archivos: el hash se calcula por bloques y el contenido permanece en disco.
    """
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


@router.post("/evidence/upload")
def upload_evidence(repository_id:str=Form(...),entity_type:str=Form(...),entity_id:str=Form(...),project_id:str|None=Form(default=None),
                    captured_at:str|None=Form(default=None),relative_folder:str|None=Form(default=None),file:UploadFile=File(...),
                    db:Session=Depends(get_db),user:User=Depends(require("evidence.manage"))):
    repo=db.get(EvidenceRepository,repository_id)
    if not repo or not repo.active:raise HTTPException(404,"Repositorio no encontrado/activo")
    root=_repository_root(repo);project=db.get(Project,project_id) if project_id else None;now=datetime.now(timezone.utc)
    capture=None
    if captured_at:
        try:capture=datetime.fromisoformat(captured_at.replace("Z","+00:00"))
        except ValueError:raise HTTPException(422,"captured_at inválido")
    if relative_folder:
        parts=[_safe_component(x) for x in Path(relative_folder).parts if x not in (".","..","/")]
    else:
        parts=[_safe_component(project.code if project else "SIN_PROYECTO"),_safe_component(entity_type),_safe_component(entity_id),f"{now.year:04d}",f"{now.month:02d}"]
    folder=root.joinpath(*parts);folder.mkdir(parents=True,exist_ok=True)
    safe=_safe_component(Path(file.filename or "evidencia.bin").name)

    # Escribimos primero a un archivo temporal en el MISMO filesystem del
    # repositorio y calculamos SHA-256 mientras llega el stream. ``os.replace``
    # hace la promoción final atómica y evita dejar una evidencia parcial con
    # nombre definitivo si se interrumpe la red/NAS.
    digest = hashlib.sha256(); size = 0
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".server-oficina-", suffix=".part", dir=folder, delete=False) as tmp:
            tmp_path = Path(tmp.name)
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk); size += len(chunk); tmp.write(chunk)
            tmp.flush(); os.fsync(tmp.fileno())
        hexdigest=digest.hexdigest();target=folder/f"{hexdigest[:12]}-{safe}"
        os.replace(tmp_path,target);tmp_path=None
    except OSError as exc:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise HTTPException(503,f"No fue posible escribir la evidencia en el repositorio: {exc}") from exc
    relative=str(target.relative_to(root))
    row=EvidenceRecord(repository_id=repo.id,entity_type=_code(entity_type),entity_id=entity_id,project_id=project_id,original_name=safe,
                       relative_path=relative,sha256=hexdigest,size_bytes=size,mime_type=file.content_type or mimetypes.guess_type(safe)[0],captured_at=capture,
                       source="UPLOAD",uploaded_by=user.id,metadata_json={"canonical_uri":repo.canonical_uri})
    db.add(row);db.commit();db.refresh(row);return {"id":row.id,"sha256":hexdigest,"relative_path":relative,"repository":repo.code}


@router.get("/locate")
def locate(q:str,db:Session=Depends(get_db),user:User=Depends(require("dashboard.view"))):
    term=q.strip()
    if len(term)<2:raise HTTPException(422,"Ingrese al menos 2 caracteres")
    like=f"%{term}%";person_ids=select(EmploymentEngagement.person_id).where(EmploymentEngagement.employment_id.ilike(like))
    people=db.scalars(select(Person).where(or_(Person.full_name.ilike(like),Person.id.in_(person_ids))).limit(20)).all()
    asset_ids=select(AssetIdentifier.asset_id).where(AssetIdentifier.value.ilike(like));assets=db.scalars(select(Asset).where(or_(Asset.internal_code.ilike(like),Asset.serial_number.ilike(like),Asset.id.in_(asset_ids))).limit(30)).all()
    pout=[]
    for p in people:
        eng=db.scalar(select(EmploymentEngagement).where(EmploymentEngagement.person_id==p.id).order_by(EmploymentEngagement.start_date.desc()))
        ass=db.scalar(select(PersonAssignment).where(PersonAssignment.person_id==p.id,PersonAssignment.end_at.is_(None)).order_by(PersonAssignment.start_at.desc()))
        custody=db.scalars(select(Asset).where(Asset.custodian_person_id==p.id,Asset.active.is_(True))).all()
        pout.append({"id":p.id,"name":p.full_name,"active":p.active,"employment_id":eng.employment_id if eng else None,"position":eng.position if eng else None,
                     "project_id":ass.project_id if ass else (eng.project_id if eng else None),"group_id":ass.group_id if ass else None,"location_id":ass.location_id if ass else None,
                     "supervisor_person_id":ass.supervisor_person_id if ass else None,"unit_asset_id":ass.unit_asset_id if ass else None,
                     "assets":[{"id":a.id,"label":_asset_label(db,a),"status":a.status_code} for a in custody]})
    aout=[]
    for a in assets:
        last=db.scalar(select(AssetMovement).where(AssetMovement.asset_id==a.id).order_by(AssetMovement.occurred_at.desc()))
        aout.append({"id":a.id,"label":_asset_label(db,a),"status":a.status_code,"project_id":a.current_project_id,"group_id":a.current_group_id,
                     "location_id":a.current_location_id,"custodian_person_id":a.custodian_person_id,
                     "last_movement":None if not last else {"type":last.movement_type,"occurred_at":last.occurred_at,"line":last.line_code,"stake":last.stake_code}})
    return {"query":term,"persons":pout,"assets":aout}

@router.get("/groups")
def groups(project_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(WorkGroup)
    if project_id:
        stmt = stmt.where(WorkGroup.project_id == project_id)
    return [{"id": g.id, "code": g.code, "name": g.name, "project_id": g.project_id}
            for g in db.scalars(stmt.order_by(WorkGroup.name)).all()]


def _project_material_snapshot(db: Session, project_id: str) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Proyecto no encontrado")
    historical_ids = set(db.scalars(select(AssetMovement.asset_id).where(AssetMovement.project_id == project_id)).all())
    current_ids = set(db.scalars(select(Asset.id).where(Asset.current_project_id == project_id)).all())
    ids = historical_ids | current_ids
    assets = db.scalars(select(Asset).where(Asset.id.in_(ids)).order_by(Asset.internal_code, Asset.serial_number)).all() if ids else []
    status_cfg = {x.code: x for x in db.scalars(select(CatalogItem).where(CatalogItem.catalog == "ASSET_STATUS")).all()}
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    rows=[]
    critical=[]
    transferable=[]
    for asset in assets:
        typ = db.get(AssetType, asset.asset_type_id)
        status_counts[asset.status_code] = status_counts.get(asset.status_code, 0) + 1
        type_code = typ.code if typ else "UNKNOWN"
        type_counts[type_code] = type_counts.get(type_code, 0) + 1
        cfg = status_cfg.get(asset.status_code)
        meta = (cfg.metadata_json or {}) if cfg else {}
        moves = db.scalars(select(AssetMovement).where(AssetMovement.asset_id == asset.id, AssetMovement.project_id == project_id).order_by(AssetMovement.occurred_at)).all()
        maint = db.scalars(select(MaintenanceOrder).where(MaintenanceOrder.asset_id == asset.id).order_by(MaintenanceOrder.opened_at)).all()
        row={
            "asset_id": asset.id, "label": _asset_label(db, asset), "type_code": type_code,
            "status_code": asset.status_code, "current_project_id": asset.current_project_id,
            "movement_count": len(moves), "maintenance_count": len(maint),
            "first_movement_at": moves[0].occurred_at.isoformat() if moves else None,
            "last_movement_at": moves[-1].occurred_at.isoformat() if moves else None,
            "transferable": bool(meta.get("transferable", False)), "critical": bool(meta.get("critical", False)),
        }
        rows.append(row)
        if row["critical"]: critical.append(row)
        if row["transferable"] and asset.active: transferable.append(row)
    return {
        "project": {"id": project.id, "code": project.code, "name": project.name, "status": project.status,
                    "start_date": project.start_date.isoformat() if project.start_date else None,
                    "end_date": project.end_date.isoformat() if project.end_date else None},
        "assets_total": len(rows), "status_counts": status_counts, "type_counts": type_counts,
        "critical_assets": critical, "transferable_assets": transferable, "assets": rows,
    }


@router.get("/projects/{project_id}/material-closeout")
def project_material_closeout_preview(project_id: str, db: Session = Depends(get_db), user: User = Depends(require("inventory.closeout"))):
    """Vista previa reproducible del corte; no cambia estado del proyecto."""
    return _project_material_snapshot(db, project_id)


@router.post("/projects/{project_id}/material-closeout")
def create_project_material_closeout(project_id: str, data: ProjectCloseoutIn, db: Session = Depends(get_db), user: User = Depends(require("inventory.closeout"))):
    """Cierra el proyecto y conserva un snapshot inmutable del material.

    El corte no mueve activos ni da de baja material; las transferencias al
    siguiente proyecto se registran después como movimientos explícitos.
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Proyecto no encontrado")
    snapshot = _project_material_snapshot(db, project_id)
    row = ProjectCloseout(project_id=project_id, created_by=user.id, note=data.note, snapshot_json=snapshot)
    project.status = "CLOSED"
    project.end_date = data.end_date or date.today()
    db.add(row); db.flush()
    audit(db, user_id=user.id, action="PROJECT_MATERIAL_CLOSEOUT", entity_type="PROJECT", entity_id=project.id,
          after={"closeout_id": row.id, "assets_total": snapshot["assets_total"], "end_date": str(project.end_date)})
    db.commit(); db.refresh(row)
    return {"id": row.id, "project_id": project.id, "project_status": project.status, "snapshot": row.snapshot_json}


@router.get("/projects/{project_id}/material-closeouts")
def project_material_closeout_history(project_id: str, db: Session = Depends(get_db), user: User = Depends(require("assets.view"))):
    rows = db.scalars(select(ProjectCloseout).where(ProjectCloseout.project_id == project_id).order_by(ProjectCloseout.created_at.desc())).all()
    return [{"id": x.id, "created_at": x.created_at, "created_by": x.created_by, "note": x.note, "snapshot": x.snapshot_json} for x in rows]


@router.get("/inventory/sessions")
def inventory_sessions(db: Session = Depends(get_db), user: User = Depends(require("assets.view"))):
    rows = db.scalars(select(InventorySession).order_by(InventorySession.started_at.desc()).limit(200)).all()
    return [{"id": x.id, "name": x.name, "project_id": x.project_id, "location_id": x.location_id,
             "status": x.status, "started_at": x.started_at, "closed_at": x.closed_at} for x in rows]

class EvidenceExistingIn(BaseModel):
    repository_id: str
    entity_type: str
    entity_id: str
    relative_path: str
    project_id: str | None = None
    captured_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


@router.post("/evidence/register-existing")
def register_existing_evidence(data: EvidenceExistingIn, db: Session = Depends(get_db), user: User = Depends(require("evidence.manage"))):
    """Indexa un archivo que ya fue copiado al NAS por Windows/organizador.

    Nunca mueve ni renombra el original. Así se puede mantener el flujo histórico
    de mapear una unidad SMB en Windows y posteriormente vincular la evidencia a
    una persona, activo, operación o caso dentro de Server Oficina.
    """
    repo = db.get(EvidenceRepository, data.repository_id)
    if not repo or not repo.active:
        raise HTTPException(404, "Repositorio no encontrado/activo")
    root = _repository_root(repo)
    candidate = (root / data.relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        raise HTTPException(422, "Ruta fuera del repositorio")
    if not candidate.is_file():
        raise HTTPException(404, "Archivo no encontrado en el repositorio")
    digest, size = _sha256_file(candidate)
    existing = db.scalar(select(EvidenceRecord).where(EvidenceRecord.repository_id == repo.id, EvidenceRecord.sha256 == digest,
                                                       EvidenceRecord.entity_type == _code(data.entity_type), EvidenceRecord.entity_id == data.entity_id))
    if existing:
        return {"id": existing.id, "sha256": existing.sha256, "already_registered": True}
    row = EvidenceRecord(repository_id=repo.id, entity_type=_code(data.entity_type), entity_id=data.entity_id,
                         project_id=data.project_id, original_name=candidate.name, relative_path=str(candidate.relative_to(root)),
                         sha256=digest, size_bytes=size, mime_type=mimetypes.guess_type(candidate.name)[0],
                         captured_at=data.captured_at, source="EXISTING_FILE", uploaded_by=user.id, metadata_json=data.metadata)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "sha256": digest, "already_registered": False}


@router.get("/evidence/records")
def evidence_records(entity_type: str | None = None, entity_id: str | None = None, project_id: str | None = None,
                     db: Session = Depends(get_db), user: User = Depends(require("evidence.view"))):
    stmt = select(EvidenceRecord)
    if entity_type: stmt = stmt.where(EvidenceRecord.entity_type == _code(entity_type))
    if entity_id: stmt = stmt.where(EvidenceRecord.entity_id == entity_id)
    if project_id: stmt = stmt.where(EvidenceRecord.project_id == project_id)
    rows = db.scalars(stmt.order_by(EvidenceRecord.created_at.desc()).limit(300)).all()
    return [{"id": x.id, "repository_id": x.repository_id, "entity_type": x.entity_type, "entity_id": x.entity_id,
             "project_id": x.project_id, "original_name": x.original_name, "relative_path": x.relative_path,
             "sha256": x.sha256, "size_bytes": x.size_bytes, "mime_type": x.mime_type, "captured_at": x.captured_at,
             "source": x.source, "created_at": x.created_at, "metadata": x.metadata_json} for x in rows]

@router.post("/engagements/{engagement_id}/organizations")
def link_engagement_organization(engagement_id: str, data: EngagementOrganizationIn, db: Session = Depends(get_db), user: User = Depends(require("person.edit"))):
    eng = db.get(EmploymentEngagement, engagement_id)
    org = db.get(Organization, data.organization_id)
    if not eng: raise HTTPException(404, "Relación laboral no encontrada")
    if not org: raise HTTPException(404, "Organización no encontrada")
    if data.end_date and data.start_date and data.end_date < data.start_date: raise HTTPException(422, "Periodo inválido")
    row = EngagementOrganizationLink(engagement_id=eng.id, organization_id=org.id, relation_type=_code(data.relation_type),
                                     start_date=data.start_date, end_date=data.end_date)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "organization_id": org.id, "relation_type": row.relation_type}


@router.get("/engagements/{engagement_id}/organizations")
def engagement_organizations(engagement_id: str, db: Session = Depends(get_db), user: User = Depends(require("person.view"))):
    rows = db.scalars(select(EngagementOrganizationLink).where(EngagementOrganizationLink.engagement_id == engagement_id)).all()
    out=[]
    for x in rows:
        org=db.get(Organization,x.organization_id)
        out.append({"id":x.id,"organization_id":x.organization_id,"organization_name":org.name if org else None,
                    "organization_type":org.organization_type if org else None,"relation_type":x.relation_type,
                    "start_date":x.start_date,"end_date":x.end_date})
    return out
