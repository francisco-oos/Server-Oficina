from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def uid() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


user_roles = Table(
    "user_roles", Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)
role_permissions = Table(
    "role_permissions", Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    permissions: Mapped[list[Permission]] = relationship(secondary=role_permissions, lazy="selectin")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160), default="")
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin")


class SessionToken(Base):
    __tablename__ = "session_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Person(Base):
    __tablename__ = "persons"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    full_name: Mapped[str] = mapped_column(String(240), index=True)
    normalized_name: Mapped[str] = mapped_column(String(240), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EmploymentEngagement(Base):
    __tablename__ = "employment_engagements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    employment_id: Mapped[str] = mapped_column(String(80), index=True)
    employer_type: Mapped[str] = mapped_column(String(30), default="DIRECT")
    provider: Mapped[str | None] = mapped_column(String(160), nullable=True)
    position: Mapped[str | None] = mapped_column(String(160), nullable=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    __table_args__ = (UniqueConstraint("employment_id", "start_date", name="uq_engagement_id_start"),)


class ContractPeriod(Base):
    __tablename__ = "contract_periods"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    engagement_id: Mapped[str] = mapped_column(ForeignKey("employment_engagements.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(160), nullable=True)


class WorkGroup(Base):
    __tablename__ = "work_groups"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_group_project_code"),)


class GroupAssignment(Base):
    __tablename__ = "group_assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("work_groups.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    attendance_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30))
    import_batch_id: Mapped[str | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True)
    __table_args__ = (UniqueConstraint("person_id", "attendance_date", name="uq_attendance_person_date"),)


class EppRequest(Base):
    __tablename__ = "epp_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    item_type: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class EppHistory(Base):
    __tablename__ = "epp_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    item_type: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(40))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    request_id: Mapped[str | None] = mapped_column(ForeignKey("epp_requests.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TrainingCourse(Base):
    __tablename__ = "training_courses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))


class TrainingRecord(Base):
    __tablename__ = "training_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("training_courses.id"), index=True)
    state: Mapped[str] = mapped_column(String(30), default="WAITLIST", index=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    scheduled_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class CaseRecord(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), nullable=True, index=True)
    case_type: Mapped[str] = mapped_column(String(100), index=True)
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    reported_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class OperationalEvent(Base):
    __tablename__ = "operational_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    source_type: Mapped[str] = mapped_column(String(80), default="SYSTEM")
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="PREVIEW", index=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImportIssue(Base):
    __tablename__ = "import_issues"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issue_type: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="OPEN")


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)

# ---------------------------------------------------------------------------
# Alpha.3 - núcleo operativo configurable
# ---------------------------------------------------------------------------
# Estas tablas amplían el monolito sin modificar las tablas alpha.2 existentes.
# Esto permite actualizar una instalación real con ``metadata.create_all`` sin
# romper datos previos.  Los estados/configuraciones se guardan como catálogos
# editables; las semillas iniciales NO son un universo hardcodeado.

class CatalogItem(Base):
    __tablename__ = "catalog_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    catalog: Mapped[str] = mapped_column(String(80), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("catalog", "code", name="uq_catalog_code"),)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    organization_type: Mapped[str] = mapped_column(String(60), default="COMPANY")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class EngagementOrganizationLink(Base):
    __tablename__ = "engagement_organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    engagement_id: Mapped[str] = mapped_column(ForeignKey("employment_engagements.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[str] = mapped_column(String(40), default="EMPLOYER")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class PersonHRProfile(Base):
    __tablename__ = "person_hr_profiles"
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    license_number: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    license_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    license_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    rotation_on_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rotation_off_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    location_type: Mapped[str] = mapped_column(String(80), default="OTHER", index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PersonAssignment(Base):
    __tablename__ = "person_assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("work_groups.id"), nullable=True, index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    supervisor_person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), nullable=True, index=True)
    unit_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)
    role_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class EmploymentLifecycleEvent(Base):
    __tablename__ = "employment_lifecycle_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    engagement_id: Mapped[str] = mapped_column(ForeignKey("employment_engagements.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AssetType(Base):
    __tablename__ = "asset_types"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Capacidades: node_field, custody, maintenance, transport, health, imei...
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AssetTechnology(Base):
    __tablename__ = "asset_technologies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    vendor: Mapped[str | None] = mapped_column(String(180), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    asset_type_id: Mapped[str] = mapped_column(ForeignKey("asset_types.id"), index=True)
    technology_id: Mapped[str | None] = mapped_column(ForeignKey("asset_technologies.id"), nullable=True, index=True)
    internal_code: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True, index=True)
    serial_number: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    status_code: Mapped[str] = mapped_column(String(80), default="AVAILABLE", index=True)
    condition_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    current_project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    current_group_id: Mapped[str | None] = mapped_column(ForeignKey("work_groups.id"), nullable=True, index=True)
    current_location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    custodian_person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class AssetIdentifier(Base):
    __tablename__ = "asset_identifiers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[str] = mapped_column(String(200), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("kind", "value", name="uq_asset_identifier_kind_value"),)


class AssetCustody(Base):
    __tablename__ = "asset_custody"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("work_groups.id"), nullable=True, index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    assignment_type: Mapped[str] = mapped_column(String(80), default="CUSTODY")
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    assigned_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssetMovement(Base):
    __tablename__ = "asset_movements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    movement_type: Mapped[str] = mapped_column(String(80), index=True)
    status_after: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("work_groups.id"), nullable=True, index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    responsible_person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), nullable=True, index=True)
    line_code: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    stake_code: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(80), default="UI")
    source_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    participant_person_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class NodeOperation(Base):
    __tablename__ = "node_operations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    operation_type: Mapped[str] = mapped_column(String(80), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("work_groups.id"), nullable=True, index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    line_code: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    participant_person_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_type: Mapped[str] = mapped_column(String(80), default="UI")
    source_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class NodeOperationItem(Base):
    __tablename__ = "node_operation_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    operation_id: Mapped[str] = mapped_column(ForeignKey("node_operations.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    stake_from: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stake_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    result_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    previous_status_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    new_status_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    responsible_person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class MaintenanceOrder(Base):
    __tablename__ = "maintenance_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(80), default="OPEN", index=True)
    priority: Mapped[str] = mapped_column(String(40), default="NORMAL")
    symptom: Mapped[str | None] = mapped_column(Text, nullable=True)
    fault_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(String(80), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    downtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opened_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class MaintenancePart(Base):
    __tablename__ = "maintenance_parts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    maintenance_order_id: Mapped[str] = mapped_column(ForeignKey("maintenance_orders.id", ondelete="CASCADE"), index=True)
    component_type: Mapped[str] = mapped_column(String(120))
    serial_removed: Mapped[str | None] = mapped_column(String(160), nullable=True)
    serial_installed: Mapped[str | None] = mapped_column(String(160), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssetHealthObservation(Base):
    __tablename__ = "asset_health_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    source: Mapped[str] = mapped_column(String(120), default="MANUAL")
    soh_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rul_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    health_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cycles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operating_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recorded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class InventorySession(Base):
    __tablename__ = "inventory_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(180))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class InventoryCount(Base):
    __tablename__ = "inventory_counts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("inventory_sessions.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    found: Mapped[bool] = mapped_column(Boolean, default=True)
    observed_status_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    counted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    counted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("session_id", "asset_id", name="uq_inventory_session_asset"),)




class ProjectCloseout(Base):
    """Corte auditable de material al cerrar un proyecto.

    El JSON es deliberadamente un snapshot: aunque después un activo sea
    transferido o reparado, el cierre histórico conserva lo que se sabía en
    ese momento y quién lo generó.
    """
    __tablename__ = "project_closeouts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

class EvidenceRepository(Base):
    __tablename__ = "evidence_repositories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    repository_type: Mapped[str] = mapped_column(String(40), default="LOCAL")
    mount_point: Mapped[str] = mapped_column(Text)
    canonical_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("evidence_repositories.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    relative_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="UPLOAD")
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
