from __future__ import annotations

import hashlib
import shutil
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
from app.db.models import (AuditLog, CaseRecord, ContractPeriod, EmploymentEngagement, EppHistory, EppRequest, Evidence,
    GroupAssignment, ImportBatch, ImportIssue, OperationalEvent, Person, Project, Role, TrainingCourse, TrainingRecord, User, WorkGroup)
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
def list_roles(db: Session = Depends(get_db), user: User = Depends(require("users.manage"))):
    return [{"name": r.name, "description": r.description, "permissions": sorted(p.code for p in r.permissions)} for r in db.scalars(select(Role).order_by(Role.name)).all()]

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require("dashboard.view"))):
    persons = db.scalar(select(func.count()).select_from(Person).where(Person.active.is_(True))) or 0
    pending_epp = db.scalar(select(func.count()).select_from(EppRequest).where(EppRequest.status == "PENDING")) or 0
    open_cases = db.scalar(select(func.count()).select_from(CaseRecord).where(CaseRecord.status == "OPEN")) or 0
    wait_training = db.scalar(select(func.count()).select_from(TrainingRecord).where(TrainingRecord.state.in_(["WAITLIST", "SCHEDULED"]))) or 0
    recent = db.scalars(select(OperationalEvent).order_by(OperationalEvent.recorded_at.desc()).limit(12)).all()
    return {"active_persons": persons, "pending_epp": pending_epp, "open_cases": open_cases, "pending_training": wait_training,
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
