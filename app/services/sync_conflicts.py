from __future__ import annotations

"""Reconocimiento conservador de copias de conflicto creadas por Syncthing."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.services.sync_path_policy import validate_portable_office_path

_CONFLICT_RE = re.compile(
    r"^(?P<stem>.+)\.sync-conflict-(?P<date>\d{8})-(?P<time>\d{6})"
    r"(?:-(?P<modified_by>[^.]+))?(?P<suffix>\.[^/]+)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SyncthingConflictName:
    conflict_path: str
    original_path: str
    date: str
    time: str
    modified_by: str | None


def parse_syncthing_conflict_path(relative_path: str) -> SyncthingConflictName | None:
    path = validate_portable_office_path(relative_path)
    pure = PurePosixPath(path)
    match = _CONFLICT_RE.match(pure.name)
    if not match:
        return None
    original_name = match.group("stem") + (match.group("suffix") or "")
    original = str(pure.with_name(original_name))
    return SyncthingConflictName(
        conflict_path=path,
        original_path=original,
        date=match.group("date"),
        time=match.group("time"),
        modified_by=match.group("modified_by"),
    )
