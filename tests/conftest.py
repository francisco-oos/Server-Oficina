import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "test.db"
if TEST_DB.exists(): TEST_DB.unlink()
os.environ["SERVER_OFICINA_ENV"] = "test"
os.environ["SERVER_OFICINA_DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB}"
os.environ["SERVER_OFICINA_DATA_DIR"] = str(Path(__file__).parent / "runtime")

import pytest
from fastapi.testclient import TestClient
from app.db.base import Base, SessionLocal, engine
from app.main import app

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture()
def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()
