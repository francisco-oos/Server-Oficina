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
    sync_root: Path
    versions_root: Path
    syncthing_api: str
    syncthing_api_key: str
    workstation_session_days: int
    workstation_online_minutes: int


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

    sync_root = Path(os.getenv("SERVER_OFICINA_SYNC_ROOT", str(data_dir / "files"))).resolve()
    versions_root = Path(os.getenv("SERVER_OFICINA_VERSIONS_ROOT", str(data_dir / "versions"))).resolve()

    return Settings(
        env=env,
        database_url=database_url,
        data_dir=data_dir,
        session_hours=int(os.getenv("SERVER_OFICINA_SESSION_HOURS", "12")),
        cookie_secure=os.getenv("SERVER_OFICINA_COOKIE_SECURE", "false").lower() == "true",
        host=os.getenv("SERVER_OFICINA_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVER_OFICINA_PORT", "8080")),
        sync_root=sync_root,
        versions_root=versions_root,
        syncthing_api=os.getenv("SERVER_OFICINA_SYNCTHING_API", "http://127.0.0.1:8384"),
        syncthing_api_key=os.getenv("SERVER_OFICINA_SYNCTHING_API_KEY", ""),
        workstation_session_days=int(os.getenv("SERVER_OFICINA_WORKSTATION_SESSION_DAYS", "15")),
        workstation_online_minutes=int(os.getenv("SERVER_OFICINA_WORKSTATION_ONLINE_MINUTES", "5")),
    )
