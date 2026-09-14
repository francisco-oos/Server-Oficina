"""Punto de entrada de la aplicación Server Oficina.

Monolito modular: un solo proceso FastAPI sirve la API y la interfaz web
estática. Los routers se registran aquí y cada uno vive en su propio módulo por
dominio, de modo que varios programadores puedan trabajar en paralelo sin
colisionar en un único archivo de rutas.

Arranque (``lifespan``)
-----------------------
El arranque es **idempotente y aditivo**: crea las tablas que falten, siembra
permisos, perfiles base, catálogos operativos y las vistas resumen semilla. Una
instalación ya existente puede promoverse a esta versión sin migración manual
porque las tablas nuevas se agregan y ninguna existente cambia de forma.

Lo que el arranque NO hace: pisar configuración del operador. Los catálogos
editados, los perfiles personalizados y la composición de los dashboards se
respetan tal como estén.
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
from app.api.routes_transport import router as transport_router
from app.db.base import Base, SessionLocal, engine
from app.services.bootstrap import ensure_operational_catalogs, ensure_rbac
from app.services.dashboards import ensure_dashboards


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_rbac(db)
        ensure_operational_catalogs(db)
        # Debe ir después de ensure_rbac: la siembra de dashboards consulta el
        # catálogo de widgets, y cada widget declara un permiso que ya debe
        # existir en base de datos para que la matriz sea coherente.
        ensure_dashboards(db)
    yield


app = FastAPI(title="Server Oficina", version=__version__, lifespan=lifespan)

# Orden de registro sin efecto funcional: los prefijos no se solapan. Se listan
# agrupados por dominio para que sea evidente dónde vive cada área.
app.include_router(router)            # núcleo heredado: RRHH, activos, nodos, taller, inventario, evidencias
app.include_router(areas_router)      # áreas y matriz de autoridad sobre el dato
app.include_router(dashboard_router)  # vista resumen configurable y modo DEV
app.include_router(dossier_router)    # búsqueda transversal y expedientes por dominio
app.include_router(transport_router)  # dominio de Transporte

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def index():
    """Sirve la aplicación web. Toda la navegación ocurre en el cliente."""
    return FileResponse(static_dir / "index.html")
