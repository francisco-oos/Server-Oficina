import pytest

from app.services.sync_core import compare_vectors, merge_vectors, normalize_relative_path, semantic_three_way_merge


def test_safe_relative_paths():
    assert normalize_relative_path(r"RRHH\2026\personal.xlsx") == "RRHH/2026/personal.xlsx"
    for bad in ("", "../secreto.xlsx", "/etc/passwd", "RRHH/../secreto.xlsx"):
        with pytest.raises(ValueError):
            normalize_relative_path(bad)


def test_vector_clock_detects_concurrency():
    assert compare_vectors({"A": 1}, {"A": 2}).relation == "BEFORE"
    assert compare_vectors({"A": 2}, {"A": 1}).relation == "AFTER"
    assert compare_vectors({"A": 1, "B": 2}, {"A": 2, "B": 1}).relation == "CONCURRENT"
    assert merge_vectors({"A": 1, "B": 2}, {"A": 3, "C": 1}) == {"A": 3, "B": 2, "C": 1}


def test_semantic_three_way_merge_non_overlapping_changes():
    base = [{"serial": "R-058", "status": "OK", "owner": "Paco"}]
    left = [{"serial": "R-058", "status": "DAMAGED", "owner": "Paco"}]
    right = [{"serial": "R-058", "status": "OK", "owner": "Juan"}]
    result = semantic_three_way_merge(base, left, right, key_field="serial")
    assert result.can_auto_merge is True
    assert result.conflicts == []
    assert result.merged == [{"serial": "R-058", "owner": "Juan", "status": "DAMAGED"}]


def test_semantic_three_way_merge_same_field_conflict_never_picks_winner():
    base = [{"serial": "R-058", "status": "OK"}]
    left = [{"serial": "R-058", "status": "DAMAGED"}]
    right = [{"serial": "R-058", "status": "AVAILABLE"}]
    result = semantic_three_way_merge(base, left, right, key_field="serial")
    assert result.can_auto_merge is False
    assert result.merged[0]["status"] == "OK"
    assert result.conflicts[0]["field"] == "status"
