"""Punto de entrada de la aplicación Server Oficina.

Monolito modular: un solo proceso FastAPI sirve la API y la interfaz web
estática. Los routers se registran aquí y cada uno vive en su propio módulo por
dominio.

El arranque es idempotente y aditivo: crea las tablas que falten y conserva
configuración existente.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import router
from app.api.routes_areas import router as areas_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_dossier import router as dossier_router
from app.api.routes_local_cloud import router as local_cloud_router
from app.api.routes_transport import router as transport_router
from app.db import local_cloud_models as _local_cloud_models  # noqa: F401 -- registra tablas aditivas
from app.db.base import Base, SessionLocal, engine
from app.services.bootstrap import ensure_operational_catalogs, ensure_rbac
from app.services.dashboards import ensure_dashboards


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_rbac(db)
        ensure_operational_catalogs(db)
        ensure_dashboards(db)
    yield


app = FastAPI(title="Server Oficina", version=__version__, lifespan=lifespan)

app.include_router(router)
app.include_router(areas_router)
app.include_router(dashboard_router)
app.include_router(dossier_router)
app.include_router(transport_router)
app.include_router(local_cloud_router)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def index():
    """Sirve la aplicación web. Toda la navegación ocurre en el cliente."""
    return FileResponse(static_dir / "index.html")
