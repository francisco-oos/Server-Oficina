"""Verificación sintáctica que NO escribe en el árbol de código.

Sustituye a ``python -m compileall`` en los gates de validación. ``compileall``
tiene como propósito *escribir* ``__pycache__``; sobre una release instalada en
modo sólo lectura eso falla o ensucia el árbol desplegado. Para el gate sólo
interesa detectar ``SyntaxError``, y ``compile()`` en memoria da exactamente esa
garantía sin efectos secundarios en disco.

Uso: ``python3 scripts/syntax-check.py app tests run.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

#: Directorios que nunca deben analizarse: no son código fuente del producto.
EXCLUDED_DIRS = {"__pycache__", ".venv", ".git", "node_modules"}


def iter_sources(targets: list[str]):
    for target in targets:
        path = Path(target)
        if path.is_file():
            yield path
        else:
            for candidate in sorted(path.rglob("*.py")):
                if EXCLUDED_DIRS.isdisjoint(candidate.parts):
                    yield candidate


def main(argv: list[str]) -> int:
    targets = argv[1:] or ["app", "tests", "run.py"]
    failures: list[str] = []
    checked = 0
    for source in iter_sources(targets):
        try:
            compile(source.read_text(encoding="utf-8"), str(source), "exec")
        except SyntaxError as exc:
            failures.append(f"{source}:{exc.lineno}: {exc.msg}")
        else:
            checked += 1
    for failure in failures:
        print(failure, file=sys.stderr)
    if failures:
        return 1
    print(f"SYNTAX_OK ({checked} archivos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
