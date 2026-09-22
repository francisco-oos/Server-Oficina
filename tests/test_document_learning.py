from app.services.document_learning import answer_clarification, create_clarification, resolve_mapping


def test_unknown_header_becomes_area_scoped_learning_rule(db):
    assert resolve_mapping(
        db, area_code="HSE", document_family="DRIVER_TRAINING",
        raw_label="VIG. M.D.", surrounding_labels=["NOMBRE", "CURSO"],
    ) is None
    clarification = create_clarification(
        db, area_code="HSE", document_family="DRIVER_TRAINING",
        raw_label="VIG. M.D.", surrounding_labels=["NOMBRE", "CURSO"],
        proposed_field="vigencia_manejo_defensivo",
    )
    assert "VIG. M.D." in clarification.question
    answer_clarification(
        db, clarification, canonical_field="training.expiration_date",
        user_id=None, remember=True,
    )
    learned = resolve_mapping(
        db, area_code="HSE", document_family="DRIVER_TRAINING",
        raw_label="VIG. M.D.", surrounding_labels=["CURSO", "NOMBRE"],
    )
    assert learned == "training.expiration_date"
    assert resolve_mapping(
        db, area_code="MATERIAL", document_family="RADIO_DELIVERY",
        raw_label="VIG. M.D.", surrounding_labels=["NOMBRE", "CURSO"],
    ) is None


def test_human_correction_can_replace_previous_mapping(db):
    clarification = create_clarification(
        db, area_code="MATERIAL", document_family="RADIO_DELIVERY",
        raw_label="RESP.", surrounding_labels=["SERIE", "FECHA"],
        proposed_field="responsible_person",
    )
    answer_clarification(db, clarification, canonical_field="responsiva_number", user_id=None, remember=True)
    assert resolve_mapping(
        db, area_code="MATERIAL", document_family="RADIO_DELIVERY",
        raw_label="RESP.", surrounding_labels=["SERIE", "FECHA"],
    ) == "responsiva_number"
