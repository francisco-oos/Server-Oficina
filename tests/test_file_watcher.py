from pathlib import Path

from app.services.file_watcher import snapshot, stable_changes


def test_watcher_ignores_office_temporaries_and_requires_two_stable_observations(tmp_path: Path):
    (tmp_path / "RRHH").mkdir()
    (tmp_path / "RRHH" / "personal.xlsx").write_bytes(b"v1")
    (tmp_path / "RRHH" / "~$personal.xlsx").write_bytes(b"lock")
    (tmp_path / "RRHH" / "temp.partial").write_bytes(b"x")
    first = snapshot(tmp_path)
    second = snapshot(tmp_path)
    assert list(first) == ["rrhh/personal.xlsx"]
    stable = stable_changes(first, second)
    assert [x.relative_path for x in stable] == ["RRHH/personal.xlsx"]
