from __future__ import annotations

"""Aprendizaje operacional de formatos sin reentrenar pesos del LLM."""

import hashlib
import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import DocumentClarification, DocumentLearningRule


def normalize_label(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip().upper()


def context_signature(labels: list[str]) -> str:
    normalized = "|".join(sorted({normalize_label(x) for x in labels if normalize_label(x)}))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def resolve_mapping(
    db: Session,
    *,
    area_code: str,
    document_family: str,
    raw_label: str,
    surrounding_labels: list[str] | None = None,
) -> str | None:
    label = normalize_label(raw_label)
    signature = context_signature(surrounding_labels or [])
    rules = db.scalars(
        select(DocumentLearningRule).where(
            DocumentLearningRule.area_code == area_code.upper(),
            DocumentLearningRule.document_family == document_family.upper(),
            DocumentLearningRule.normalized_label == label,
            DocumentLearningRule.active.is_(True),
        ).order_by(DocumentLearningRule.approved_at.desc())
    ).all()
    if not rules:
        return None
    exact = next((r for r in rules if r.context_signature == signature), None)
    generic = next((r for r in rules if not r.context_signature), None)
    return (exact or generic).canonical_field if (exact or generic) else None


def create_clarification(
    db: Session,
    *,
    area_code: str,
    document_family: str,
    raw_label: str,
    surrounding_labels: list[str] | None = None,
    version_id: str | None = None,
    proposed_field: str | None = None,
) -> DocumentClarification:
    label = normalize_label(raw_label)
    signature = context_signature(surrounding_labels or [])
    proposal = {"canonical_field": proposed_field} if proposed_field else {}
    question = f"Detecté una columna nueva: {raw_label}. ¿A qué dato corresponde?"
    if proposed_field:
        question = f"Detecté una columna nueva: {raw_label}. ¿Corresponde a {proposed_field}?"
    row = DocumentClarification(
        version_id=version_id,
        area_code=area_code.upper(),
        document_family=document_family.upper(),
        raw_label=raw_label,
        normalized_label=label,
        context_signature=signature,
        question=question,
        proposal_json=proposal,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def answer_clarification(
    db: Session,
    clarification: DocumentClarification,
    *,
    canonical_field: str,
    user_id: str | None,
    remember: bool = True,
) -> DocumentLearningRule | None:
    if clarification.status != "OPEN":
        raise ValueError("La aclaración ya fue respondida")
    clarification.status = "ANSWERED"
    clarification.answer_json = {"canonical_field": canonical_field, "remember": remember}
    clarification.answered_by = user_id
    clarification.answered_at = datetime.now(timezone.utc)
    rule = None
    if remember:
        rule = db.scalar(select(DocumentLearningRule).where(
            DocumentLearningRule.area_code == clarification.area_code,
            DocumentLearningRule.document_family == clarification.document_family,
            DocumentLearningRule.normalized_label == clarification.normalized_label,
            DocumentLearningRule.context_signature == clarification.context_signature,
        ))
        if rule is None:
            rule = DocumentLearningRule(
                area_code=clarification.area_code,
                document_family=clarification.document_family,
                normalized_label=clarification.normalized_label,
                canonical_field=canonical_field,
                context_signature=clarification.context_signature,
                approved_by=user_id,
            )
            db.add(rule)
        else:
            rule.canonical_field = canonical_field
            rule.approved_by = user_id
            rule.approved_at = datetime.now(timezone.utc)
            rule.active = True
    db.commit()
    return rule
