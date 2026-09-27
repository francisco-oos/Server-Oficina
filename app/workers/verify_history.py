from __future__ import annotations

"""Verifica la consistencia entre DocumentVersion (base) y el ContentStore (disco).

Uso (en la Latitude, como serveroficina o root, con el env de producción):

    python -m app.workers.verify_history            # existencia + tamaño
    python -m app.workers.verify_history --deep     # además recalcula SHA-256

Salida: ``HISTORY_OK`` o ``HISTORY_FAIL`` con conteos. Nunca borra ni repara:
los objetos no referenciados se informan (p. ej. copias de una ingesta
interrumpida) y los faltantes/corruptos exigen revisión humana y restore.
Códigos de salida: 0 correcto, 3 faltantes, 4 corruptos (tiene precedencia).
"""

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

from app.core.config import load_settings
from app.db import local_cloud_models as _local_cloud_models  # noqa: F401
from app.db.base import SessionLocal
from app.db.local_cloud_models import DocumentRecord, DocumentVersion
from app.services.content_store import ContentStore, sha256_file


@dataclass
class HistoryReport:
    referenced: int = 0
    missing: list[str] = field(default_factory=list)
    corrupt: list[str] = field(default_factory=list)
    unreferenced: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.corrupt

    @property
    def exit_code(self) -> int:
        return 4 if self.corrupt else 3 if self.missing else 0


def verify_history(db, store: ContentStore, *, deep: bool = False, share_id: str | None = None) -> HistoryReport:
    report = HistoryReport()
    expected: dict[str, int] = {}
    query = (
        select(DocumentVersion.sha256, DocumentVersion.size_bytes)
        .where(DocumentVersion.storage_relative_path.is_not(None))
        .where(DocumentVersion.change_kind != "DELETED")
    )
    if share_id:
        query = query.join(DocumentRecord, DocumentRecord.id == DocumentVersion.document_id).where(
            DocumentRecord.share_id == share_id)
    for sha, size in db.execute(query).all():
        expected[sha] = size
    report.referenced = len(expected)
    for sha, size in sorted(expected.items()):
        path = store.path_for(sha)
        if not path.is_file():
            report.missing.append(sha)
        elif path.stat().st_size != size or (deep and sha256_file(path) != sha):
            report.corrupt.append(sha)
    base = store.root / "sha256"
    if base.is_dir() and not share_id:
        for candidate in base.glob("*/*"):
            if candidate.is_file() and not candidate.name.startswith(".") and candidate.name not in expected:
                report.unreferenced.append(candidate.name)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verificar historial Server Oficina (DB ↔ versions/)")
    parser.add_argument("--deep", action="store_true", help="recalcular SHA-256 de cada objeto")
    args = parser.parse_args()
    settings = load_settings()
    store = ContentStore(settings.versions_root)
    with SessionLocal() as db:
        report = verify_history(db, store, deep=args.deep)
    verdict = "HISTORY_OK" if report.ok else "HISTORY_FAIL"
    print(
        f"{verdict} versions_root={store.root} referenciados={report.referenced} "
        f"faltantes={len(report.missing)} corruptos={len(report.corrupt)} "
        f"no_referenciados={len(report.unreferenced)} profundo={args.deep}"
    )
    for sha in report.missing[:20]:
        print(f"FALTANTE {sha}")
    for sha in report.corrupt[:20]:
        print(f"CORRUPTO {sha}")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
