"""Resolución de la ubicación de escritura que usa la suite de pruebas.

Problema que resuelve
---------------------
Una release promovida queda instalada en ``/opt/server-oficina/current`` y es
**de sólo lectura** para el usuario que ejecuta la validación manual. La suite
anterior fijaba la base SQLite y ``SERVER_OFICINA_DATA_DIR`` *dentro del árbol
de código* (``tests/test.db`` y ``tests/runtime/``). Durante la instalación eso
funcionaba porque el instalador corre como root sobre un árbol todavía
escribible, pero al ejecutar ``VALIDAR_SERVER_OFICINA.sh`` después, contra la
release ya instalada, la importación del ``conftest`` fallaba con
``PermissionError`` antes de recolectar una sola prueba.

Decisión de arquitectura
------------------------
Las pruebas NO deben escribir nunca dentro del árbol de código. Toda la
escritura vive en un directorio *runtime* independiente que se elige en este
orden:

1. ``SERVER_OFICINA_TEST_RUNTIME`` si el operador la define (útil para
   inspeccionar los artefactos después de una corrida, o para apuntar a un
   volumen concreto en CI);
2. un directorio temporal privado del sistema operativo.

La alternativa descartada fue debilitar permisos (``chmod -R 777`` o hacer
escribible ``/opt``): eso convierte el código desplegado en modificable por
cualquier usuario y contradice el endurecimiento del servicio systemd.

Efecto secundario deliberado: cuando el directorio se crea aquí (no lo impuso
el operador), se registra para borrado al terminar el proceso, de modo que una
validación manual repetida no acumule basura en ``/tmp``.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

#: Variable de entorno con la que un operador fija explícitamente el runtime.
ENV_VAR = "SERVER_OFICINA_TEST_RUNTIME"

_runtime_dir: Path | None = None


def runtime_dir() -> Path:
    """Devuelve el directorio escribible de la suite, creándolo una sola vez.

    Es idempotente dentro del proceso: varias llamadas devuelven la misma ruta,
    para que la base de datos, el ``data_dir`` de la aplicación y la caché de
    pytest compartan la misma raíz y se limpien juntas.
    """
    global _runtime_dir
    if _runtime_dir is not None:
        return _runtime_dir

    configured = os.environ.get(ENV_VAR, "").strip()
    if configured:
        # Ruta impuesta por el operador: se respeta y NO se borra al terminar.
        path = Path(configured).expanduser()
        path.mkdir(parents=True, exist_ok=True)
    else:
        path = Path(tempfile.mkdtemp(prefix="server-oficina-tests-"))
        atexit.register(shutil.rmtree, path, True)

    _runtime_dir = path.resolve()
    return _runtime_dir
