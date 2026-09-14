"""Arranque de la suite de pruebas de Server Oficina.

Este módulo se ejecuta **antes** de importar la aplicación porque
``app.db.base`` resuelve la configuración (y crea el ``data_dir``) en tiempo de
importación. Por eso las variables de entorno se fijan aquí arriba y no dentro
de una fixture.

Invariante importante: ninguna ruta de escritura apunta al árbol de código.
Ver ``tests/_runtime.py`` para el razonamiento completo.
"""

import os

from tests._runtime import runtime_dir

RUNTIME = runtime_dir()
TEST_DB = RUNTIME / "server_oficina_test.db"
DATA_DIR = RUNTIME / "data"

# Cada corrida parte de una base limpia: las pruebas comparten un único cliente
# de sesión y asumen que el primer administrador todavía no existe.
if TEST_DB.exists():
    TEST_DB.unlink()
DATA_DIR.mkdir(parents=True, exist_ok=True)

os.environ["SERVER_OFICINA_ENV"] = "test"
os.environ["SERVER_OFICINA_DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB}"
os.environ["SERVER_OFICINA_DATA_DIR"] = str(DATA_DIR)

import pytest  # noqa: E402  (debe importarse después de fijar el entorno)
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    """Cliente HTTP con el ciclo de vida real de la aplicación.

    Usar ``with TestClient(app)`` es deliberado: dispara el ``lifespan``, que a
    su vez crea el esquema y siembra RBAC y catálogos operativos. Probar contra
    un esquema sembrado a mano ocultaría regresiones del arranque real.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
