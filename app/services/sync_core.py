from __future__ import annotations

"""Primitivas seguras de sincronización y reconciliación.

No implementa un sincronizador de bloques: esa responsabilidad se delega a un
motor probado (Syncthing). Aquí viven las invariantes de Server Oficina:
rutas confinadas, relojes vectoriales para razonar sobre concurrencia y merge
semántico de tres vías sólo cuando el documento tiene una clave estable.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable


def normalize_relative_path(value: str) -> str:
    raw = (value or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/") or "\x00" in raw:
        raise ValueError("Ruta relativa inválida")
    path = PurePosixPath(raw)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("La ruta contiene segmentos no permitidos")
    return "/".join(path.parts)


@dataclass(frozen=True)
class VectorOrder:
    relation: str


def compare_vectors(left: dict[str, int], right: dict[str, int]) -> VectorOrder:
    keys = set(left) | set(right)
    left_le = all(int(left.get(k, 0)) <= int(right.get(k, 0)) for k in keys)
    right_le = all(int(right.get(k, 0)) <= int(left.get(k, 0)) for k in keys)
    if left_le and right_le:
        return VectorOrder("EQUAL")
    if left_le:
        return VectorOrder("BEFORE")
    if right_le:
        return VectorOrder("AFTER")
    return VectorOrder("CONCURRENT")


def merge_vectors(*vectors: dict[str, int]) -> dict[str, int]:
    keys = set().union(*(v.keys() for v in vectors))
    return {key: max(int(v.get(key, 0)) for v in vectors) for key in sorted(keys)}


@dataclass(frozen=True)
class MergeResult:
    merged: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    can_auto_merge: bool


_MISSING = object()


def _index(rows: Iterable[dict[str, Any]], key_field: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if key_field not in row or row[key_field] in (None, ""):
            raise ValueError(f"Registro sin clave estable {key_field}")
        key = str(row[key_field])
        if key in out:
            raise ValueError(f"Clave duplicada en documento: {key}")
        out[key] = dict(row)
    return out


def semantic_three_way_merge(
    base_rows: Iterable[dict[str, Any]],
    left_rows: Iterable[dict[str, Any]],
    right_rows: Iterable[dict[str, Any]],
    *,
    key_field: str,
) -> MergeResult:
    """Merge de tres vías a nivel registro/campo, inspirado en Git.

    Sólo es válido cuando la familia documental tiene una clave estable
    previamente aprobada (serie, employment_id, etc.). Nunca fusiona bytes XLSX.
    """
    base, left, right = _index(base_rows, key_field), _index(left_rows, key_field), _index(right_rows, key_field)
    merged: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for key in sorted(set(base) | set(left) | set(right)):
        b, l, r = base.get(key), left.get(key), right.get(key)

        if b is None:
            if l is None:
                merged.append(r)
            elif r is None:
                merged.append(l)
            elif l == r:
                merged.append(l)
            else:
                conflicts.append({"key": key, "kind": "CONCURRENT_ADD", "left": l, "right": r})
            continue

        if l is None and r is None:
            continue
        if l is None:
            if r == b:
                continue
            conflicts.append({"key": key, "kind": "DELETE_VS_EDIT", "left": None, "right": r, "base": b})
            continue
        if r is None:
            if l == b:
                continue
            conflicts.append({"key": key, "kind": "EDIT_VS_DELETE", "left": l, "right": None, "base": b})
            continue

        row = {key_field: l.get(key_field, r.get(key_field, b.get(key_field)))}
        fields = set(b) | set(l) | set(r)
        for field in sorted(fields - {key_field}):
            bv, lv, rv = b.get(field, _MISSING), l.get(field, _MISSING), r.get(field, _MISSING)
            l_changed, r_changed = lv != bv, rv != bv
            if l_changed and r_changed and lv != rv:
                conflicts.append({
                    "key": key, "field": field, "kind": "FIELD_CONFLICT",
                    "base": None if bv is _MISSING else bv,
                    "left": None if lv is _MISSING else lv,
                    "right": None if rv is _MISSING else rv,
                })
                if bv is not _MISSING:
                    row[field] = bv
            elif r_changed:
                if rv is not _MISSING:
                    row[field] = rv
            elif l_changed:
                if lv is not _MISSING:
                    row[field] = lv
            elif bv is not _MISSING:
                row[field] = bv
        merged.append(row)

    return MergeResult(merged=merged, conflicts=conflicts, can_auto_merge=not conflicts)
