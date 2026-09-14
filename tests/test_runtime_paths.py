"""Pruebas del aislamiento de rutas de escritura de la suite.

Fijan la corrección del problema reportado: ejecutar
``VALIDAR_SERVER_OFICINA.sh`` a mano contra la release instalada en
``/opt/server-oficina/current`` fallaba con ``PermissionError`` porque las
pruebas escribían dentro del árbol de código.

La corrección NO debilita permisos de ``/opt`` ni usa ``chmod -R 777``: mueve
toda la escritura a un runtime temporal. Estas pruebas impiden que alguien
vuelva a apuntar la base de datos o el ``data_dir`` al árbol desplegado.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.core.config import load_settings
from tests._runtime import ENV_VAR, runtime_dir

#: Raíz del repositorio/release. Ningún artefacto de prueba debe caer aquí.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def test_runtime_dir_is_outside_the_source_tree():
    runtime = runtime_dir()
    assert runtime.exists() and runtime.is_dir()
    assert not _is_inside(runtime, PROJECT_ROOT), (
        f"El runtime de pruebas quedó dentro del árbol de código: {runtime}. "
        "Una release instalada en modo sólo lectura fallaría con PermissionError."
    )


def test_runtime_dir_is_stable_within_the_process():
    """Base de datos, data_dir y artefactos deben compartir una sola raíz."""
    assert runtime_dir() == runtime_dir()


def test_database_and_data_dir_do_not_touch_the_source_tree():
    database_url = os.environ["SERVER_OFICINA_DATABASE_URL"]
    assert database_url.startswith("sqlite"), "La suite debe correr contra SQLite aislado"
    db_path = Path(database_url.split("///", 1)[1])
    assert not _is_inside(db_path, PROJECT_ROOT), f"La base de pruebas quedó en el árbol: {db_path}"

    settings = load_settings()
    assert not _is_inside(settings.data_dir, PROJECT_ROOT), (
        f"SERVER_OFICINA_DATA_DIR quedó en el árbol: {settings.data_dir}"
    )
    # El data_dir real debe existir con sus subcarpetas: la aplicación las crea
    # al cargar la configuración y las pruebas de evidencias dependen de ello.
    for child in ("imports", "evidence", "backups"):
        assert (settings.data_dir / child).is_dir()


def test_no_stale_artefacts_are_written_into_the_source_tree():
    """Los artefactos que causaban el fallo no deben reaparecer en el árbol."""
    prohibidos = [
        PROJECT_ROOT / "tests" / "runtime",
        PROJECT_ROOT / "tests" / "test.db",
        PROJECT_ROOT / ".pytest_cache",
    ]
    presentes = [str(p.relative_to(PROJECT_ROOT)) for p in prohibidos if p.exists()]
    assert not presentes, (
        f"La suite volvió a escribir dentro del árbol de código: {presentes}. "
        "Debe usar el runtime temporal de tests/_runtime.py."
    )


def test_operator_can_pin_the_runtime_location():
    """El operador puede fijar el runtime para inspeccionarlo tras una corrida."""
    assert ENV_VAR == "SERVER_OFICINA_TEST_RUNTIME"
    # Se documenta el contrato sin re-ejecutar la resolución: runtime_dir() es
    # idempotente por proceso a propósito, para que la base y el data_dir no se
    # separen a mitad de la suite.
    assert runtime_dir().is_absolute()
