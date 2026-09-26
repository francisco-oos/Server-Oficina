from pathlib import Path

import pytest

from app.services.file_watcher import snapshot
from app.services.sync_path_policy import PathCollisionError, portable_path_key, validate_portable_office_path


def test_portable_key_normalizes_case_and_unicode():
    assert portable_path_key("RRHH/CAFÉ.xlsx") == portable_path_key("rrhh/CAFE\u0301.xlsx")


@pytest.mark.parametrize("path", [
    "Material/CON.xlsx",
    "Material/archivo?.xlsx",
    "Material/nombre. ",
])
def test_windows_incompatible_names_are_rejected(path):
    with pytest.raises(ValueError):
        validate_portable_office_path(path)


def test_snapshot_ignores_office_and_syncthing_temporaries(tmp_path: Path):
    (tmp_path / "Material").mkdir()
    (tmp_path / "Material" / "real.xlsx").write_bytes(b"real")
    (tmp_path / "Material" / "~$real.xlsx").write_bytes(b"office")
    (tmp_path / "Material" / "~syncthing~real.xlsx.tmp").write_bytes(b"sync")
    (tmp_path / "Material" / ".syncthing.real.xlsx.tmp").write_bytes(b"sync")
    snap = snapshot(tmp_path)
    assert list(snap) == ["material/real.xlsx"]


def test_snapshot_detects_case_collision_before_windows_receives_it(tmp_path: Path):
    (tmp_path / "Material").mkdir()
    (tmp_path / "Material" / "Radio.xlsx").write_bytes(b"a")
    (tmp_path / "Material" / "radio.xlsx").write_bytes(b"b")
    with pytest.raises(PathCollisionError):
        snapshot(tmp_path)
