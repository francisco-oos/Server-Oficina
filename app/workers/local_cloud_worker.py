from __future__ import annotations

"""Observador de carpetas canónicas del hub. Nunca modifica ni borra archivos.

Semántica (ver docs/arquitectura/53_FASE_1_SINCRONIZACION_OBSERVADOR.md):

* ``DELETED`` sólo se registra cuando la raíz del share es confiable y un
  archivo ya registrado deja de existir.
* Una raíz ausente, sin permisos, con error de E/S, sin marcador ``.stfolder``
  (share Syncthing), montada sobre otro dispositivo o vacía sin poder
  verificarse deja el share ``UNAVAILABLE``: no se registra ningún borrado.
* Los problemas de un archivo concreto se aíslan y quedan como evidencia en el
  journal y en ``SyncShare.metadata_json["observer"]``.
"""

import argparse
import errno
import os
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import func, select

from app.core.config import load_settings
from app.db import local_cloud_models as _local_cloud_models  # noqa: F401
from app.db.base import SessionLocal
from app.db.local_cloud_models import DocumentRecord, SyncPeer, SyncShare
from app.services.content_store import ContentStore
from app.services.file_watcher import (
    FileObservation,
    PathIssue,
    ShareScanError,
    _is_systemic,
    ingest_missing_documents,
    ingest_stable_snapshot,
    scan_tree,
    stable_changes,
)
from app.services.sync_path_policy import portable_path_key
from app.services.syncthing_attribution import SyncthingAttributor, short_device_id

Log = Callable[[str], None]

#: Cuántas incidencias por share se exponen en la API (el journal las tiene todas).
MAX_REPORTED_ISSUES = 50


def _log(message: str) -> None:
    print(message, flush=True)


@dataclass
class ShareState:
    """Estado en memoria de un share entre pasadas del observador.

    ``processed`` recuerda la huella ``(tamaño, mtime, inodo, ctime)`` ya
    evaluada para no recalcular SHA-256 de archivos sin cambios; sólo vive en
    memoria y nunca reescribe el historial. ``root_dev`` fija el dispositivo de
    la raíz para detectar un montaje ausente o sustituido.
    """

    observations: dict[str, FileObservation]
    processed: dict[str, tuple[int, int, int, int]] = field(default_factory=dict)
    issues: set[tuple[str, str]] = field(default_factory=set)
    unavailable_code: str | None = None
    unavailable_detail: str | None = None
    root_dev: int | None = None
    store_low: bool = False
    error: str | None = None
    persisted: dict | None = None

    @property
    def unavailable(self) -> str | None:
        return self.unavailable_code


def _root_error(exc: OSError) -> tuple[str, str]:
    detail = exc.strerror or str(exc)
    if exc.errno == errno.ENOENT:
        return "ROOT_MISSING", "raíz ausente"
    if exc.errno in (errno.EACCES, errno.EPERM):
        return "ROOT_PERMISSION", f"permiso denegado: {detail}"
    if exc.errno == errno.EIO:
        return "ROOT_IO_ERROR", f"error de E/S: {detail}"
    if exc.errno == errno.ENOTDIR:
        return "ROOT_NOT_DIRECTORY", "la raíz no es un directorio"
    return "ROOT_INACCESSIBLE", f"raíz inaccesible: {detail}"


def share_root_problem(share: SyncShare, root: Path, *, allowed_root: Path | None = None) -> str | None:
    """Compatibilidad: devuelve sólo la descripción del problema de la raíz."""
    problem, _dev = _check_root(share, root, allowed_root=allowed_root)
    return problem[1] if problem else None


def _check_root(share: SyncShare, root: Path, *, allowed_root: Path | None) -> tuple[tuple[str, str] | None, int | None]:
    if allowed_root is not None:
        try:
            root.resolve().relative_to(allowed_root.resolve())
        except ValueError:
            return ("OUTSIDE_SYNC_ROOT", f"raíz fuera de SERVER_OFICINA_SYNC_ROOT ({allowed_root})"), None
    try:
        stat = os.stat(root)
        if not os.path.isdir(root):
            return ("ROOT_NOT_DIRECTORY", "la raíz no es un directorio"), None
        with os.scandir(root):  # permiso real de lectura sobre la raíz, sin listarla
            pass
        if share.syncthing_folder_id and not (root / ".stfolder").exists():
            return ("SYNCTHING_MARKER_MISSING",
                    "falta el marcador .stfolder de Syncthing (¿disco o montaje ausente?)"), stat.st_dev
    except OSError as exc:
        return _root_error(exc), None
    return None, stat.st_dev


def _live_documents(db, share: SyncShare) -> int:
    return db.scalar(select(func.count()).select_from(DocumentRecord).where(
        DocumentRecord.share_id == share.id, DocumentRecord.deleted.is_(False))) or 0


def _persist_status(db, share: SyncShare, state: ShareState, issues: list[PathIssue]) -> None:
    """Expone el estado del observador en la API sólo cuando cambia."""
    status = {
        "state": "UNAVAILABLE" if state.unavailable_code or state.error else "AVAILABLE",
        "code": state.unavailable_code or ("SHARE_ERROR" if state.error else None),
        "detail": state.unavailable_detail or state.error,
        "store_low_space": state.store_low,
        "issues_total": len(issues),
        "issues": [
            {"path": i.relative_path, "code": i.code, "reason": i.reason}
            for i in sorted(issues, key=lambda i: (i.relative_path, i.code))[:MAX_REPORTED_ISSUES]
        ],
    }
    if status == state.persisted:
        return
    metadata = dict(share.metadata_json or {})
    metadata["observer"] = {**status, "since": datetime.now(timezone.utc).isoformat()}
    share.metadata_json = metadata
    db.commit()
    state.persisted = status


def scan_share(
    db,
    *,
    share: SyncShare,
    previous: ShareState | None,
    content_store: ContentStore,
    settle_seconds: float = 1.0,
    allowed_root: Path | None = None,
    log: Log = _log,
    attribute=None,
) -> tuple[ShareState, dict[str, int]]:
    stats = {"created_versions": 0, "deletions": 0, "skipped": 0, "unavailable": 0, "errors": 0}
    root = Path(share.local_root)
    persisted = previous.persisted if previous else None
    # El dispositivo de referencia sobrevive a los estados no disponibles: sólo
    # un reinicio del observador (tras verificar el montaje) fija uno nuevo.
    baseline_dev = previous.root_dev if previous else None
    last_code = previous.unavailable_code if previous else None

    def unavailable(code: str, detail: str) -> tuple[ShareState, dict[str, int]]:
        stats["unavailable"] = 1
        if last_code != code:
            log(f"LOCAL_CLOUD_SHARE_UNAVAILABLE share={share.code} code={code} reason={detail}")
        state = ShareState(observations={}, unavailable_code=code, unavailable_detail=detail,
                           root_dev=baseline_dev, persisted=persisted)
        _persist_status(db, share, state, [])
        return state, stats

    problem, root_dev = _check_root(share, root, allowed_root=allowed_root)
    if problem:
        return unavailable(*problem)
    if baseline_dev is not None and root_dev != baseline_dev:
        return unavailable("ROOT_DEVICE_CHANGED",
                           f"la raíz cambió de dispositivo ({baseline_dev} -> {root_dev}); posible montaje "
                           "ausente o sustituido; reiniciar el observador tras verificar")
    if previous is not None and (previous.unavailable_code or previous.error):
        log(f"LOCAL_CLOUD_SHARE_AVAILABLE share={share.code}")
        previous = None

    try:
        if previous is None:
            first, _ = scan_tree(root)
            time.sleep(max(0.0, settle_seconds))
            state = ShareState(observations=first, root_dev=baseline_dev or root_dev, persisted=persisted)
        else:
            state = previous
        current, issues = scan_tree(root)
    except ShareScanError as exc:
        return unavailable(*_root_error(exc))
    # Si el disco desaparece durante el recorrido, no se registran borrados.
    problem, now_dev = _check_root(share, root, allowed_root=allowed_root)
    if problem:
        return unavailable(*problem)
    if now_dev != state.root_dev:
        return unavailable("ROOT_DEVICE_CHANGED", "la raíz cambió de dispositivo durante el recorrido")
    if not current and not issues and not share.syncthing_folder_id and _live_documents(db, share):
        # Sin marcador que pruebe que la carpeta es la real, "vacía con
        # documentos vivos" es la firma de un montaje ausente, no un borrado.
        return unavailable("ROOT_EMPTY_UNVERIFIED",
                           "raíz vacía con documentos registrados y sin marcador .stfolder")

    state.processed = {k: v for k, v in state.processed.items() if k in current}
    pending = [
        item for item in stable_changes(state.observations, current)
        if state.processed.get(portable_path_key(item.relative_path)) != item.fingerprint
    ]
    headroom = content_store.headroom_bytes()
    if headroom <= 0:
        if not state.store_low:
            log(f"LOCAL_CLOUD_STORE_LOW_SPACE share={share.code} versions_root={content_store.root} "
                f"headroom_bytes={headroom}; archivado en pausa")
        state.store_low = True
        pending = []
    elif state.store_low:
        log(f"LOCAL_CLOUD_STORE_OK share={share.code} headroom_bytes={headroom}")
        state.store_low = False

    errors: list[PathIssue] = []
    stats["created_versions"] = ingest_stable_snapshot(
        db, share=share, root=root, stable=pending, content_store=content_store,
        errors=errors, attribute=attribute,
    )
    failed = {issue.key for issue in errors}
    for item in pending:
        key = portable_path_key(item.relative_path)
        if key not in failed:
            state.processed[key] = item.fingerprint

    all_issues = issues + errors
    stats["deletions"] = ingest_missing_documents(
        db, share=share, current=current,
        protected={i.key for i in all_issues if i.key and not i.prefix},
        protected_prefixes={i.key for i in all_issues if i.key and i.prefix},
    )
    stats["skipped"] = len(all_issues)

    seen = set()
    for issue in all_issues:
        marker = (issue.relative_path, issue.code)
        seen.add(marker)
        if marker not in state.issues:
            log(f"LOCAL_CLOUD_SKIP share={share.code} code={issue.code} "
                f"path={issue.relative_path!r} reason={issue.reason}")
    state.issues = seen
    state.observations = current
    _persist_status(db, share, state, all_issues)
    return state, stats


def scan_share_isolated(db, *, share: SyncShare, previous: ShareState | None, **kwargs) -> tuple[ShareState, dict[str, int]]:
    """Un fallo inesperado en un share no detiene a los demás.

    Los errores sistémicos del disco (ENOSPC, EROFS, EIO en el ContentStore)
    sí se elevan: el proceso termina y systemd lo reinicia de forma visible.
    """
    log = kwargs.get("log", _log)
    try:
        return scan_share(db, share=share, previous=previous, **kwargs)
    except Exception as exc:
        if _is_systemic(exc):
            raise
        db.rollback()
        summary = f"{exc.__class__.__name__}: {exc}"
        if previous is None or previous.error != summary:
            log(f"LOCAL_CLOUD_SHARE_ERROR share={share.code} error={summary}\n{traceback.format_exc()}")
        state = ShareState(observations={}, error=summary, persisted=previous.persisted if previous else None)
        try:
            _persist_status(db, share, state, [])
        except Exception:  # noqa: BLE001 - la base puede ser la causa del error
            db.rollback()
        return state, {"created_versions": 0, "deletions": 0, "skipped": 0, "unavailable": 0, "errors": 1}


def preflight_content_store(root: Path) -> int:
    """Falla de inmediato si el ContentStore no es escribible (error sistémico).

    Además elimina temporales ``.partial-*`` de copias interrumpidas; devuelve
    cuántos borró. Es seguro porque el observador es el único escritor.
    """
    root.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".preflight-", dir=root)
    try:
        os.write(fd, b"ok")
        os.fsync(fd)
    finally:
        os.close(fd)
        os.unlink(name)
    return ContentStore(root).remove_orphan_partials()


def _attributor_factory(db, settings, log: Log):
    """Atribución técnica por ``modifiedBy`` de Syncthing si hay API key configurada."""
    if not settings.syncthing_api_key:
        return lambda _share: None
    from app.services.syncthing_adapter import SyncthingClient

    try:
        client = SyncthingClient(settings.syncthing_api, settings.syncthing_api_key, timeout=3.0)
    except ValueError as exc:
        log(f"LOCAL_CLOUD_ATTRIBUTION_DISABLED reason={exc}")
        return lambda _share: None
    peers = {
        short_device_id(p.syncthing_device_id): (p.id, p.code)
        for p in db.scalars(select(SyncPeer).where(SyncPeer.syncthing_device_id.is_not(None))).all()
    }

    def build(share: SyncShare):
        if not share.syncthing_folder_id:
            return None
        return SyncthingAttributor(client, folder_id=share.syncthing_folder_id, peers_by_short_id=peers, log=log)

    return build


def run_once(
    previous_by_share: dict[str, ShareState] | None = None,
    *,
    settle_seconds: float = 1.0,
    log: Log = _log,
):
    previous_by_share = previous_by_share or {}
    totals = {"created_versions": 0, "deletions": 0, "shares": 0, "skipped": 0, "unavailable": 0, "errors": 0}
    next_state: dict[str, ShareState] = {}
    settings = load_settings()
    content_store = ContentStore(settings.versions_root, min_free_percent=settings.versions_min_free_percent)

    with SessionLocal() as db:
        attributor_for = _attributor_factory(db, settings, log)
        shares = db.scalars(select(SyncShare).where(SyncShare.active.is_(True))).all()
        for share in shares:
            state, stats = scan_share_isolated(
                db,
                share=share,
                previous=previous_by_share.get(share.id),
                content_store=content_store,
                settle_seconds=settle_seconds,
                allowed_root=settings.sync_root,
                log=log,
                attribute=attributor_for(share),
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
    orphans = preflight_content_store(settings.versions_root)
    _log(
        f"LOCAL_CLOUD_START sync_root={settings.sync_root} "
        f"versions_root={settings.versions_root} interval={args.interval} "
        f"min_free_percent={settings.versions_min_free_percent} "
        f"attribution={'syncthing' if settings.syncthing_api_key else 'none'} "
        f"orphan_partials_removed={orphans}"
    )
    state: dict[str, ShareState] = {}
    previous_line = None
    cycle = 0
    while True:
        state, totals = run_once(state, settle_seconds=args.settle)
        line = (
            f"LOCAL_CLOUD_SCAN shares={totals['shares']} "
            f"versions={totals['created_versions']} deletions={totals['deletions']} "
            f"skipped={totals['skipped']} unavailable={totals['unavailable']} errors={totals['errors']}"
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
