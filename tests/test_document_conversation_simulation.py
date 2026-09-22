from uuid import uuid4

from app.services.document_learning import (
    answer_clarification,
    create_clarification,
    resolve_mapping,
)


def test_four_areas_can_teach_same_label_without_mixing_context(db):
    """La enseñanza pertenece al área/familia, nunca a una memoria global."""
    scenarios = [
        ("RRHH", "PERSONAL_STATUS", "UBIC.", "person.location"),
        ("HSE", "TRAINING", "VIG.", "training.expiration_date"),
        ("TRANSPORTE", "LICENSES", "VIG.", "license.expiration_date"),
        ("MATERIAL", "RADIOS", "RESP.", "responsiva_number"),
    ]
    for area, family, label, canonical in scenarios:
        question = create_clarification(
            db,
            area_code=area,
            document_family=family,
            raw_label=label,
            surrounding_labels=["NOMBRE", "FECHA", uuid4().hex[:6]],
            proposed_field=canonical,
        )
        assert question.status == "OPEN"
        assert label in question.question
        answer_clarification(
            db, question, canonical_field=canonical, user_id=None, remember=True
        )

    assert resolve_mapping(
        db, area_code="HSE", document_family="TRAINING",
        raw_label="VIG.", surrounding_labels=["NOMBRE", "FECHA"]
    ) is None  # contexto distinto: debe preguntar, no adivinar


def test_operator_can_answer_without_retraining_model(db):
    """Una respuesta humana se vuelve regla reproducible y auditable."""
    labels = ["SERIE", "ESTADO", "FECHA"]
    row = create_clarification(
        db,
        area_code="MATERIAL",
        document_family="ASSET_HISTORY",
        raw_label="COND.",
        surrounding_labels=labels,
        proposed_field="asset.condition",
    )
    answer_clarification(
        db, row, canonical_field="asset.condition", user_id=None, remember=True
    )
    assert resolve_mapping(
        db,
        area_code="MATERIAL",
        document_family="ASSET_HISTORY",
        raw_label="COND.",
        surrounding_labels=list(reversed(labels)),
    ) == "asset.condition"
