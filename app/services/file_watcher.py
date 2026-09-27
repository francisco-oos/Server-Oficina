from __future__ import annotations

"""Escaneo incremental de las carpetas canónicas de la Latitude.

Contrato de integridad (ver docs/arquitectura/53_FASE_1_SINCRONIZACION_OBSERVADOR.md):

* Un archivo se ingiere sólo cuando dos observaciones consecutivas tienen la
  misma huella ``(tamaño, mtime_ns, inodo, ctime_ns)``.
* El SHA-256 se reutiliza (no se recalcula) únicamente si la huella actual es
  idéntica a la registrada en la última versión o a la ya procesada en este
  proceso. Cualquier diferencia —incluido un reemplazo con igual tamaño y
  mtime, que cambia el inodo o el ctime— obliga a recalcular.
* Tras calcular el hash y archivar, la huella se vuelve a leer: si el archivo
  cambió durante la ingesta no se registra nada y se reintenta más tarde.
"""

import errno
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.local_cloud_models import DocumentRecord, DocumentVersion, SyncShare
from app.services.content_store import ContentStore
from app.services.document_registry import register_version
from app.services.sync_conflicts import parse_syncthing_conflict_path
from app.services.sync_path_policy import PathCollisionError, portable_path_key, validate_portable_office_path

IGNORED_SUFFIXES = {".tmp", ".partial", ".part", ".swp"}
IGNORED_DIRS = {".stversions", ".stfolder"}

#: Errores del almacenamiento de la Latitude (no de un archivo concreto) que
#: deben detener el observador durante la ingesta en vez de aislarse.
SYSTEMIC_ERRNOS = {errno.ENOSPC, errno.EROFS, errno.EDQUOT, errno.EIO, errno.ENOMEM}


@dataclass(frozen=True)
class FileObservation:
    """Archivo visto en disco.

    ``relative_path`` es la ruta lógica normalizada (NFC); ``disk_relative_path``
    es el nombre exacto en disco, que puede diferir (NFD, espacios) y es el
    único válido para abrir el archivo.
    """

    relative_path: str
    size_bytes: int
    mtime_ns: int
    inode: int = 0
    ctime_ns: int = 0
    disk_relative_path: str | None = None

    @property
    def disk_path(self) -> str:
        return self.disk_relative_path or self.relative_path

    @property
    def fingerprint(self) -> tuple[int, int, int, int]:
        return (self.size_bytes, self.mtime_ns, self.inode, self.ctime_ns)


@dataclass(frozen=True)
class PathIssue:
    """Elemento que no se ingiere en esta pasada y queda como evidencia.

    ``key`` protege contra tombstones el documento con esa clave; con
    ``prefix=True`` protege todo el subárbol (directorio ilegible).
    """

    relative_path: str
    reason: str
    key: str | None = None
    error: Exception | None = None
    code: str = "INGEST_DEFERRED"
    prefix: bool = False


class ShareScanError(OSError):
    """La raíz del share no pudo recorrerse: fallo del recurso, no borrado."""


class ChangedDuringIngest(OSError):
    """La huella del archivo cambió entre la observación estable y el archivado."""


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


def _fingerprint(stat: os.stat_result) -> tuple[int, int, int, int]:
    return (stat.st_size, stat.st_mtime_ns, stat.st_ino, stat.st_ctime_ns)


def scan_tree(root: Path) -> tuple[dict[str, FileObservation], list[PathIssue]]:
    """Observa la carpeta sin abortar por un archivo problemático.

    Nombres no portables, colisiones de mayúsculas/Unicode (posibles en el hub
    Linux cuando dos PCs Windows trabajaron offline), symlinks y entradas que
    desaparecen durante el recorrido se reportan como ``PathIssue``. En una
    colisión ninguna de las rutas gana: todas quedan para revisión humana.

    Un subdirectorio ilegible protege su subárbol. Un error sobre la raíz o un
    error de E/S en cualquier punto eleva ``ShareScanError``: el share queda no
    disponible y nunca se interpreta como borrado.
    """
    root = root.resolve()
    out: dict[str, FileObservation] = {}
    issues: list[PathIssue] = []
    if not root.exists():
        return out, issues
    candidates: dict[str, list[FileObservation]] = {}

    def on_walk_error(exc: OSError) -> None:
        failed = Path(exc.filename) if exc.filename else root
        if failed == root or exc.errno == errno.EIO or _is_systemic(exc):
            raise ShareScanError(exc.errno, exc.strerror, str(failed))
        if isinstance(exc, FileNotFoundError):
            return
        relative = failed.relative_to(root).as_posix() if failed.is_relative_to(root) else str(failed)
        try:
            key = portable_path_key(relative)
        except ValueError:
            key = None
        issues.append(PathIssue(relative, f"directorio ilegible: {exc.strerror}", key=key,
                                error=exc, code="SUBTREE_UNREADABLE", prefix=True))

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
                if "\\" in name:
                    raise ValueError(f"Nombre no portable en Windows: {name}")
                rel = validate_portable_office_path(rel_text)
                key = portable_path_key(rel)
            except ValueError as exc:
                issues.append(PathIssue(rel_text, str(exc), error=exc, code="NAME_NOT_PORTABLE"))
                continue
            try:
                stat = path.lstat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                if exc.errno == errno.EIO:
                    raise ShareScanError(exc.errno, exc.strerror, str(path)) from exc
                issues.append(PathIssue(rel, f"stat falló: {exc.strerror}", key=key, error=exc,
                                        code="STAT_FAILED"))
                continue
            if path.is_symlink():
                issues.append(PathIssue(rel, "symlink no soportado en carpeta sincronizada", key=key,
                                        code="SYMLINK"))
                continue
            if not os.path.isfile(path):
                continue
            candidates.setdefault(key, []).append(FileObservation(
                rel, stat.st_size, stat.st_mtime_ns, stat.st_ino, stat.st_ctime_ns,
                None if rel == rel_text else rel_text,
            ))

    for key, observations in candidates.items():
        if len(observations) == 1:
            out[key] = observations[0]
            continue
        names = " <> ".join(o.disk_path for o in observations)
        error = PathCollisionError(f"Colisión Windows/Linux: {names}")
        for observation in observations:
            issues.append(PathIssue(observation.disk_path, str(error), key=key, error=error,
                                    code="CASE_COLLISION"))
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
    """Archivos cuya huella completa no cambió entre dos observaciones."""
    return [
        item for key, item in current.items()
        if key in previous and previous[key].fingerprint == item.fingerprint
    ]


def sha256_file(path: Path, *, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _recorded_fingerprint(version: DocumentVersion) -> tuple[int, int, int, int] | None:
    stored = (version.metadata_json or {}).get("fingerprint")
    if not isinstance(stored, dict):
        return None
    try:
        return (version.size_bytes, version.mtime_ns, int(stored["inode"]), int(stored["ctime_ns"]))
    except (KeyError, TypeError, ValueError):
        return None


Attributor = Callable[[FileObservation], dict | None]


def ingest_stable_snapshot(
    db: Session,
    *,
    share: SyncShare,
    root: Path,
    stable: Iterable[FileObservation],
    source_peer_id: str | None = None,
    content_store: ContentStore | None = None,
    errors: list[PathIssue] | None = None,
    attribute: Attributor | None = None,
) -> int:
    """Registra versiones de archivos estables.

    Con ``errors`` (modo observador) un archivo que desaparece, cambia durante
    la copia, no puede leerse o no cabe en el ContentStore se reporta y se
    reintenta en la siguiente pasada sin detener el resto; los errores
    sistémicos del disco siempre se elevan. Sin ``errors`` se conserva el
    comportamiento estricto.

    ``attribute`` (opcional) devuelve la atribución técnica de dispositivo
    (p. ej. ``modifiedBy`` de Syncthing); nunca bloquea la ingesta.
    """
    count = 0
    root = root.resolve()
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
        if latest and not tombstoned and _recorded_fingerprint(latest) == observation.fingerprint:
            continue
        path = root / observation.disk_path
        try:
            if not path.resolve().is_relative_to(root):
                raise ValueError("Archivo fuera de la raíz aprobada")
            if content_store is not None and content_store.headroom_bytes() < observation.size_bytes:
                if errors is None:
                    raise OSError(errno.ENOSPC, "ContentStore sin espacio sobre la reserva")
                errors.append(PathIssue(observation.relative_path,
                                        "espacio insuficiente en versions/ sobre la reserva",
                                        key=key, code="STORE_LOW_SPACE"))
                continue
            digest = sha256_file(path)
            stored = None
            if content_store is not None:
                stored = content_store.archive_file(path, expected_sha256=digest)
            if observation.inode and _fingerprint(path.stat()) != observation.fingerprint:
                raise ChangedDuringIngest("el archivo cambió durante la ingesta")
        except (OSError, ValueError) as exc:
            if errors is None or _is_systemic(exc):
                raise
            code = "CHANGED_DURING_INGEST" if isinstance(exc, ChangedDuringIngest) else "INGEST_DEFERRED"
            errors.append(PathIssue(observation.relative_path, f"ingesta aplazada: {exc}", key=key,
                                    error=exc, code=code))
            continue
        conflict = parse_syncthing_conflict_path(observation.relative_path)
        metadata = {
            "scanner": "stable-two-pass",
            "content_archived": stored is not None,
            "syncthing_conflict": bool(conflict),
            "fingerprint": {"inode": observation.inode, "ctime_ns": observation.ctime_ns},
        }
        if conflict:
            metadata["conflict_of"] = conflict.original_path
            metadata["conflict_modified_by"] = conflict.modified_by
            metadata["conflict_observed_name"] = conflict.conflict_path
        peer_id = source_peer_id
        if attribute is not None:
            attribution = attribute(observation)
            if attribution:
                peer_id = attribution.pop("source_peer_id", None) or peer_id
                metadata["attribution"] = attribution

        document, version, created = register_version(
            db,
            share=share,
            relative_path=observation.relative_path,
            sha256=digest,
            size_bytes=stored.size_bytes if stored is not None else observation.size_bytes,
            mtime_ns=observation.mtime_ns,
            source_peer_id=peer_id,
            change_kind=(
                "CONFLICT" if conflict
                else "RECOVERED" if tombstoned and latest.sha256 == digest
                else "MODIFIED"
            ),
            storage_relative_path=stored.relative_path if stored is not None else None,
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
    protected_prefixes: Iterable[str] = (),
) -> int:
    """Registra tombstones; nunca borra físicamente ni purga versiones.

    ``protected`` contiene claves presentes en disco pero no ingeridas (p. ej.
    colisión de mayúsculas) y ``protected_prefixes`` subárboles que no pudieron
    leerse: su ausencia en ``current`` no es un borrado.
    """
    count = 0
    protected = set(protected)
    prefixes = tuple(p.rstrip("/") + "/" for p in protected_prefixes if p)
    documents = db.scalars(select(DocumentRecord).where(
        DocumentRecord.share_id == share.id,
        DocumentRecord.deleted.is_(False),
    )).all()
    for document in documents:
        path = document.normalized_path
        if path in current or path in protected or path.startswith(prefixes):
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
