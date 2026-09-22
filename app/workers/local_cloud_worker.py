from __future__ import annotations

"""Worker de observación de carpetas canónicas; no borra archivos."""

import argparse
import time
from pathlib import Path

from sqlalchemy import select

from app.db import local_cloud_models as _local_cloud_models  # noqa: F401
from app.db.base import SessionLocal
from app.db.local_cloud_models import SyncShare
from app.services.file_watcher import ingest_missing_documents, ingest_stable_snapshot, snapshot, stable_changes


def run_once(previous_by_share: dict[str, dict] | None = None, *, settle_seconds: float = 1.0):
    previous_by_share = previous_by_share or {}
    totals = {"created_versions": 0, "deletions": 0, "shares": 0}
    next_state: dict[str, dict] = {}
    with SessionLocal() as db:
        shares = db.scalars(select(SyncShare).where(SyncShare.active.is_(True))).all()
        for share in shares:
            root = Path(share.local_root)
            first = previous_by_share.get(share.id) or snapshot(root)
            if share.id not in previous_by_share:
                time.sleep(max(0.0, settle_seconds))
            current = snapshot(root)
            totals["created_versions"] += ingest_stable_snapshot(
                db, share=share, root=root, stable=stable_changes(first, current))
            totals["deletions"] += ingest_missing_documents(db, share=share, current=current)
            totals["shares"] += 1
            next_state[share.id] = current
    return next_state, totals


def main() -> int:
    parser = argparse.ArgumentParser(description="Observador Nube Local de Server Oficina")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--settle", type=float, default=1.0)
    args = parser.parse_args()
    state: dict[str, dict] = {}
    while True:
        state, totals = run_once(state, settle_seconds=args.settle)
        print(f"LOCAL_CLOUD_SCAN shares={totals['shares']} versions={totals['created_versions']} deletions={totals['deletions']}", flush=True)
        if args.once:
            return 0
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
