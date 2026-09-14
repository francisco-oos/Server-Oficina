from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    env: str
    database_url: str
    data_dir: Path
    session_hours: int
    cookie_secure: bool
    host: str
    port: int


def load_settings() -> Settings:
    env = os.getenv("SERVER_OFICINA_ENV", "development")
    database_url = os.getenv(
        "SERVER_OFICINA_DATABASE_URL",
        "sqlite+pysqlite:///./runtime/server_oficina.db",
    )
    data_dir = Path(os.getenv("SERVER_OFICINA_DATA_DIR", "./runtime")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    for child in ("imports", "evidence", "backups"):
        (data_dir / child).mkdir(parents=True, exist_ok=True)
    return Settings(
        env=env,
        database_url=database_url,
        data_dir=data_dir,
        session_hours=int(os.getenv("SERVER_OFICINA_SESSION_HOURS", "12")),
        cookie_secure=os.getenv("SERVER_OFICINA_COOKIE_SECURE", "false").lower() == "true",
        host=os.getenv("SERVER_OFICINA_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVER_OFICINA_PORT", "8080")),
    )
