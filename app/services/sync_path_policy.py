from __future__ import annotations

"""Política de nombres portables entre Windows y Linux.

La Latitude usa un filesystem sensible a mayúsculas, mientras las PCs Windows
normalmente no. Server Oficina evita aceptar dos rutas que Windows no podría
representar de forma inequívoca.
"""

import re
import unicodedata

from app.services.sync_core import normalize_relative_path

_WINDOWS_FORBIDDEN = re.compile(r'[<>:"|?*]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class PathCollisionError(ValueError):
    pass


def validate_portable_office_path(value: str) -> str:
    path = unicodedata.normalize("NFC", normalize_relative_path(value))
    for segment in path.split("/"):
        if _WINDOWS_FORBIDDEN.search(segment):
            raise ValueError(f"Nombre no portable en Windows: {segment}")
        if segment.endswith((" ", ".")):
            raise ValueError(f"Nombre termina en espacio/punto: {segment}")
        stem = segment.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED:
            raise ValueError(f"Nombre reservado por Windows: {segment}")
    return path


def portable_path_key(value: str) -> str:
    """Clave lógica única independiente de mayúsculas y forma Unicode."""
    return validate_portable_office_path(value).casefold()
