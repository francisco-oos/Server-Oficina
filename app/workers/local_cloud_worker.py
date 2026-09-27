from __future__ import annotations

"""Worker de observación de carpetas canónicas; no borra archivos."""

import argparse
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from sqlalchemy import select

from app.core.config import load_settings
from app.db import local_cloud_models as _local_cloud_models  # noqa: F401
from app.db.base import SessionLocal
from app.db.local_cloud_models import SyncShare
from app.services.content_store import ContentStore
from app.services.file_watcher import (
    FileObservation,
    PathIssue,
    ingest_missing_documents,
    ingest_stable_snapshot,
    scan_tree,
    stable_changes,
)
from app.services.sync_path_policy import portable_path_key

Log = Callable[[str], None]


def _log(message: str) -> None:
    print(message, flush=True)


@dataclass
class ShareState:
    """Estado en memoria de un share entre pasadas del observador.

    ``processed`` recuerda (tamaño, mtime) ya evaluados para no recalcular
    SHA-256 de archivos sin cambios cada pocos segundos; sólo vive en memoria,
    nunca reescribe el historial. ``issues`` y ``unavailable`` evitan repetir
    el mismo aviso en cada pasada.
    """

    observations: dict[str, FileObservation]
    processed: dict[str, tuple[int, int]] = field(default_factory=dict)
    issues: set[tuple[str, str]] = field(default_factory=set)
    unavailable: str | None = None


def share_root_problem(share: SyncShare, root: Path, *, allowed_root: Path | None = None) -> str | None:
    """Devuelve la causa si la raíz no es confiable para detectar borrados.

    Una raíz ausente, inaccesible o sin el marcador ``.stfolder`` de Syncthing
    (disco o montaje no presente) es un fallo sistémico del share: no debe
    interpretarse como que todos sus documentos fueron borrados.
    """
    if allowed_root is not None:
        try:
            root.resolve().relative_to(allowed_root.resolve())
        except ValueError:
            return f"raíz fuera de SERVER_OFICINA_SYNC_ROOT ({allowed_root})"
    try:
        if not root.is_dir():
            return "raíz ausente o no es directorio"
        if share.syncthing_folder_id and not (root / ".stfolder").exists():
            return "falta el marcador .stfolder de Syncthing (¿disco o montaje ausente?)"
    except OSError as exc:
        return f"raíz inaccesible: {exc.strerror or exc}"
    return None


def scan_share(
    db,
    *,
    share: SyncShare,
    previous: ShareState | None,
    content_store: ContentStore,
    settle_seconds: float = 1.0,
    allowed_root: Path | None = None,
    log: Log = _log,
) -> tuple[ShareState, dict[str, int]]:
    stats = {"created_versions": 0, "deletions": 0, "skipped": 0, "unavailable": 0}
    root = Path(share.local_root)

    def unavailable(problem: str) -> tuple[ShareState, dict[str, int]]:
        stats["unavailable"] = 1
        if previous is None or previous.unavailable != problem:
            log(f"LOCAL_CLOUD_SHARE_UNAVAILABLE share={share.code} reason={problem}")
        return ShareState(observations={}, unavailable=problem), stats

    problem = share_root_problem(share, root, allowed_root=allowed_root)
    if problem:
        return unavailable(problem)
    if previous is not None and previous.unavailable:
        log(f"LOCAL_CLOUD_SHARE_AVAILABLE share={share.code}")
        previous = None

    if previous is None:
        first, _ = scan_tree(root)
        time.sleep(max(0.0, settle_seconds))
        state = ShareState(observations=first)
    else:
        state = previous
    current, issues = scan_tree(root)
    # Si el disco desaparece durante el recorrido, no se registran borrados.
    problem = share_root_problem(share, root, allowed_root=allowed_root)
    if problem:
        return unavailable(problem)

    state.processed = {k: v for k, v in state.processed.items() if k in current}
    pending = [
        item for item in stable_changes(state.observations, current)
        if state.processed.get(portable_path_key(item.relative_path)) != (item.size_bytes, item.mtime_ns)
    ]
    errors: list[PathIssue] = []
    stats["created_versions"] = ingest_stable_snapshot(
        db, share=share, root=root, stable=pending, content_store=content_store, errors=errors
    )
    failed = {issue.key for issue in errors}
    for item in pending:
        key = portable_path_key(item.relative_path)
        if key not in failed:
            state.processed[key] = (item.size_bytes, item.mtime_ns)

    all_issues = issues + errors
    protected = {issue.key for issue in all_issues if issue.key}
    stats["deletions"] = ingest_missing_documents(db, share=share, current=current, protected=protected)
    stats["skipped"] = len(all_issues)

    seen = set()
    for issue in all_issues:
        marker = (issue.relative_path, issue.reason)
        seen.add(marker)
        if marker not in state.issues:
            log(f"LOCAL_CLOUD_SKIP share={share.code} path={issue.relative_path!r} reason={issue.reason}")
    state.issues = seen
    state.observations = current
    return state, stats


def preflight_content_store(root: Path) -> None:
    """Falla de inmediato si el ContentStore no es escribible (error sistémico)."""
    root.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".preflight-", dir=root)
    try:
        os.write(fd, b"ok")
        os.fsync(fd)
    finally:
        os.close(fd)
        os.unlink(name)


def run_once(
    previous_by_share: dict[str, ShareState] | None = None,
    *,
    settle_seconds: float = 1.0,
    log: Log = _log,
):
    previous_by_share = previous_by_share or {}
    totals = {"created_versions": 0, "deletions": 0, "shares": 0, "skipped": 0, "unavailable": 0}
    next_state: dict[str, ShareState] = {}
    settings = load_settings()
    content_store = ContentStore(settings.versions_root)

    with SessionLocal() as db:
        shares = db.scalars(select(SyncShare).where(SyncShare.active.is_(True))).all()
        for share in shares:
            state, stats = scan_share(
                db,
                share=share,
                previous=previous_by_share.get(share.id),
                content_store=content_store,
                settle_seconds=settle_seconds,
                allowed_root=settings.sync_root,
                log=log,
            )
            for key, value in stats.items():
                totals[key] += value
            totals["shares"] += 1
            next_state[share.id] = state
    return next_state, totals


def main() -> int:
    parser = argparse.ArgumentParser(description="Observador Nube Local de Server Oficina")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--settle", type=float, default=1.0)
    parser.add_argument(
        "--heartbeat-every", type=int, default=120,
        help="Pasadas sin cambios entre dos líneas de resumen en el journal",
    )
    args = parser.parse_args()
    settings = load_settings()
    preflight_content_store(settings.versions_root)
    _log(
        f"LOCAL_CLOUD_START sync_root={settings.sync_root} "
        f"versions_root={settings.versions_root} interval={args.interval}"
    )
    state: dict[str, ShareState] = {}
    previous_line = None
    cycle = 0
    while True:
        state, totals = run_once(state, settle_seconds=args.settle)
        line = (
            f"LOCAL_CLOUD_SCAN shares={totals['shares']} "
            f"versions={totals['created_versions']} deletions={totals['deletions']} "
            f"skipped={totals['skipped']} unavailable={totals['unavailable']}"
        )
        changed = totals["created_versions"] or totals["deletions"] or line != previous_line
        if args.once or changed or cycle % max(1, args.heartbeat_every) == 0:
            _log(line)
        previous_line = line
        cycle += 1
        if args.once:
            return 0
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
