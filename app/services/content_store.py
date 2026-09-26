from __future__ import annotations

"""Almacén local inmutable por contenido para versiones de documentos.

Syncthing transporta el archivo de trabajo. Este almacén conserva una copia
independiente en la Latitude una vez que el archivo se observa estable. Así un
borrado o reemplazo posterior en la carpeta sincronizada no elimina la evidencia
histórica ya capturada por Server Oficina.
"""

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredContent:
    sha256: str
    size_bytes: int
    relative_path: str
    created: bool


def _validate_sha256(value: str) -> str:
    value = (value or "").strip().lower()
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError("SHA-256 inválido")
    return value


def sha256_file(path: Path, *, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


class ContentStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def relative_path_for(self, sha256: str) -> str:
        digest = _validate_sha256(sha256)
        return f"sha256/{digest[:2]}/{digest}"

    def path_for(self, sha256: str) -> Path:
        target = (self.root / self.relative_path_for(sha256)).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Ruta de contenido fuera del almacén") from exc
        return target

    def archive_file(self, source: Path, *, expected_sha256: str | None = None) -> StoredContent:
        """Copia bytes de forma atómica y verifica el contenido antes de promover."""
        source = source.resolve()
        expected = _validate_sha256(expected_sha256) if expected_sha256 else sha256_file(source)
        size = source.stat().st_size
        target = self.path_for(expected)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            if target.stat().st_size != size or sha256_file(target) != expected:
                raise IOError("Contenido existente no coincide con su dirección SHA-256")
            return StoredContent(expected, size, self.relative_path_for(expected), False)

        fd, temp_name = tempfile.mkstemp(prefix=".partial-", dir=target.parent)
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as dst, source.open("rb") as src:
                shutil.copyfileobj(src, dst, length=4 * 1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            if temp.stat().st_size != size or sha256_file(temp) != expected:
                raise IOError("La copia temporal no coincide con el archivo fuente")
            os.replace(temp, target)
            os.chmod(target, 0o440)
            # Persistimos también el cambio de directorio cuando el filesystem lo soporta.
            try:
                dir_fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
        finally:
            if temp.exists():
                temp.unlink(missing_ok=True)

        return StoredContent(expected, size, self.relative_path_for(expected), True)

    def verify(self, sha256: str) -> bool:
        digest = _validate_sha256(sha256)
        target = self.path_for(digest)
        return target.is_file() and sha256_file(target) == digest

    def restore_to(self, sha256: str, destination: Path) -> Path:
        """Restaura una copia sin modificar el objeto inmutable almacenado."""
        digest = _validate_sha256(sha256)
        source = self.path_for(digest)
        if not self.verify(digest):
            raise FileNotFoundError("Versión histórica ausente o corrupta")
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".restore-", dir=destination.parent)
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as dst, source.open("rb") as src:
                shutil.copyfileobj(src, dst, length=4 * 1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            if sha256_file(temp) != digest:
                raise IOError("La restauración no superó SHA-256")
            os.replace(temp, destination)
        finally:
            if temp.exists():
                temp.unlink(missing_ok=True)
        return destination
