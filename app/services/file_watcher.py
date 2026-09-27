from __future__ import annotations

"""Escaneo incremental de las carpetas canónicas de la Latitude."""

import errno
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, SyncShare
from app.services.content_store import ContentStore
from app.services.document_registry import register_version
from app.services.sync_conflicts import parse_syncthing_conflict_path
from app.services.sync_path_policy import PathCollisionError, portable_path_key, validate_portable_office_path

IGNORED_SUFFIXES = {".tmp", ".partial", ".part", ".swp"}
IGNORED_DIRS = {".stversions", ".stfolder"}

#: Errores que indican un fallo del almacenamiento de la Latitude, no de un
#: archivo concreto: deben detener el observador en vez de aislarse.
SYSTEMIC_ERRNOS = {errno.ENOSPC, errno.EROFS, errno.EDQUOT, errno.EIO, errno.ENOMEM}


@dataclass(frozen=True)
class FileObservation:
    relative_path: str
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True)
class PathIssue:
    """Archivo que no se ingiere en esta pasada y requiere atención humana.

    ``key`` es la clave portable cuando pudo calcularse; los documentos con
    esa clave quedan protegidos contra tombstones mientras dure el problema.
    """

    relative_path: str
    reason: str
    key: str | None = None
    error: Exception | None = None


def _ignored(relative: Path) -> bool:
    if any(part in IGNORED_DIRS for part in relative.parts):
        return True
    if relative.as_posix() == ".stignore":
        return True
    if relative.name.startswith("~$"):
        return True
    if relative.name.startswith(".syncthing.") or relative.name.startswith("~syncthing~"):
        return True
    return relative.suffix.lower() in IGNORED_SUFFIXES


def _is_systemic(exc: BaseException) -> bool:
    return isinstance(exc, OSError) and exc.errno in SYSTEMIC_ERRNOS


def scan_tree(root: Path) -> tuple[dict[str, FileObservation], list[PathIssue]]:
    """Observa la carpeta sin abortar por un archivo problemático.

    Nombres no portables, colisiones de mayúsculas/Unicode (posibles en el hub
    Linux cuando dos PCs Windows trabajaron offline), symlinks y entradas que
    desaparecen durante el recorrido se reportan como ``PathIssue``. En una
    colisión ninguna de las rutas gana: todas quedan para revisión humana.
    """
    root = root.resolve()
    out: dict[str, FileObservation] = {}
    issues: list[PathIssue] = []
    if not root.exists():
        return out, issues
    candidates: dict[str, list[FileObservation]] = {}

    def on_walk_error(exc: OSError) -> None:
        if _is_systemic(exc):
            raise exc
        if isinstance(exc, FileNotFoundError):
            return
        issues.append(PathIssue(str(exc.filename or ""), f"directorio ilegible: {exc.strerror}", error=exc))

    for dirpath, dirnames, filenames in os.walk(root, onerror=on_walk_error, followlinks=False):
        base = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        for name in sorted(filenames) + [d for d in dirnames if (base / d).is_symlink()]:
            path = base / name
            relative = path.relative_to(root)
            if _ignored(relative):
                continue
            rel_text = relative.as_posix()
            try:
                rel = validate_portable_office_path(rel_text)
                key = portable_path_key(rel)
            except ValueError as exc:
                issues.append(PathIssue(rel_text, str(exc), error=exc))
                continue
            try:
                stat = path.lstat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                if _is_systemic(exc):
                    raise
                issues.append(PathIssue(rel, f"stat falló: {exc.strerror}", key=key, error=exc))
                continue
            if path.is_symlink():
                issues.append(PathIssue(rel, "symlink no soportado en carpeta sincronizada", key=key))
                continue
            if not os.path.isfile(path):
                continue
            candidates.setdefault(key, []).append(FileObservation(rel, stat.st_size, stat.st_mtime_ns))

    for key, observations in candidates.items():
        if len(observations) == 1:
            out[key] = observations[0]
            continue
        names = " <> ".join(o.relative_path for o in observations)
        error = PathCollisionError(f"Colisión Windows/Linux: {names}")
        for observation in observations:
            issues.append(PathIssue(observation.relative_path, str(error), key=key, error=error))
    return out, issues


def snapshot(root: Path) -> dict[str, FileObservation]:
    """Variante estricta: cualquier problema de ruta se eleva como excepción."""
    observations, issues = scan_tree(root)
    for issue in issues:
        if issue.error is not None:
            raise issue.error
        raise ValueError(f"{issue.relative_path}: {issue.reason}")
    return observations


def stable_changes(
    previous: dict[str, FileObservation],
    current: dict[str, FileObservation],
) -> list[FileObservation]:
    return [
        item for key, item in current.items()
        if key in previous
        and previous[key].size_bytes == item.size_bytes
        and previous[key].mtime_ns == item.mtime_ns
    ]


def sha256_file(path: Path, *, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def ingest_stable_snapshot(
    db: Session,
    *,
    share: SyncShare,
    root: Path,
    stable: Iterable[FileObservation],
    source_peer_id: str | None = None,
    content_store: ContentStore | None = None,
    errors: list[PathIssue] | None = None,
) -> int:
    """Registra versiones de archivos estables.

    Con ``errors`` (modo observador) un archivo que desaparece, cambia durante
    la copia o no puede leerse se reporta y se reintenta en la siguiente pasada
    sin detener el resto; los errores sistémicos del disco siempre se elevan.
    Sin ``errors`` se conserva el comportamiento estricto.
    """
    count = 0
    for observation in stable:
        key = portable_path_key(observation.relative_path)
        document = db.scalar(select(DocumentRecord).where(
            DocumentRecord.share_id == share.id,
            DocumentRecord.normalized_path == key,
        ))
        latest = None
        if document:
            latest = db.scalar(select(DocumentVersion).where(
                DocumentVersion.document_id == document.id
            ).order_by(DocumentVersion.observed_at.desc()))
        # Un tombstone copia mtime/tamaño de la última versión; si el archivo
        # vuelve idéntico (papelera de Windows, .stversions) debe recuperarse.
        tombstoned = latest is not None and latest.change_kind == "DELETED"
        if (latest and not tombstoned and latest.mtime_ns == observation.mtime_ns
                and latest.size_bytes == observation.size_bytes):
            continue
        path = (root / observation.relative_path).resolve()
        try:
            try:
                path.relative_to(root.resolve())
            except ValueError as exc:
                raise ValueError("Archivo fuera de la raíz aprobada") from exc
            digest = sha256_file(path)
            stored_path = None
            if content_store is not None:
                stored = content_store.archive_file(path, expected_sha256=digest)
                stored_path = stored.relative_path
        except (OSError, ValueError) as exc:
            if errors is None or _is_systemic(exc):
                raise
            errors.append(PathIssue(observation.relative_path, f"ingesta aplazada: {exc}", key=key, error=exc))
            continue
        conflict = parse_syncthing_conflict_path(observation.relative_path)
        metadata = {
            "scanner": "stable-two-pass",
            "content_archived": bool(stored_path),
            "syncthing_conflict": bool(conflict),
        }
        if conflict:
            metadata["conflict_of"] = conflict.original_path
            metadata["conflict_modified_by"] = conflict.modified_by
            metadata["conflict_observed_name"] = conflict.conflict_path

        document, version, created = register_version(
            db,
            share=share,
            relative_path=observation.relative_path,
            sha256=digest,
            size_bytes=observation.size_bytes,
            mtime_ns=observation.mtime_ns,
            source_peer_id=source_peer_id,
            change_kind=(
                "CONFLICT" if conflict
                else "RECOVERED" if tombstoned and latest.sha256 == digest
                else "MODIFIED"
            ),
            storage_relative_path=stored_path,
            metadata=metadata,
        )
        if conflict:
            document.metadata_json = {
                **(document.metadata_json or {}),
                "syncthing_conflict": True,
                "conflict_of": conflict.original_path,
            }
            version.analysis_status = "CONFLICT_REVIEW"
            db.commit()
        count += int(created)
    return count


def ingest_missing_documents(
    db: Session,
    *,
    share: SyncShare,
    current: dict[str, FileObservation],
    source_peer_id: str | None = None,
    protected: Iterable[str] = (),
) -> int:
    """Registra tombstones; nunca borra físicamente ni purga versiones.

    ``protected`` contiene claves presentes en disco pero no ingeridas (p. ej.
    colisión de mayúsculas): su ausencia en ``current`` no es un borrado.
    """
    count = 0
    protected = set(protected)
    documents = db.scalars(select(DocumentRecord).where(
        DocumentRecord.share_id == share.id,
        DocumentRecord.deleted.is_(False),
    )).all()
    for document in documents:
        if document.normalized_path in current or document.normalized_path in protected:
            continue
        latest = db.scalar(select(DocumentVersion).where(
            DocumentVersion.document_id == document.id
        ).order_by(DocumentVersion.observed_at.desc()))
        if latest is None or latest.change_kind == "DELETED":
            continue
        _, _, created = register_version(
            db,
            share=share,
            relative_path=document.logical_path,
            sha256=latest.sha256,
            size_bytes=latest.size_bytes,
            mtime_ns=latest.mtime_ns,
            source_peer_id=source_peer_id,
            change_kind="DELETED",
            parent_version_id=latest.id,
            metadata={"scanner": "missing-tombstone", "physical_purge": False},
        )
        count += int(created)
    return count
