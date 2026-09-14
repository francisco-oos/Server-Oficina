"""Gate de contrato del frontend.

Verifica, sin navegador, que la interfaz publicada cumple los compromisos
estructurales del producto. No sustituye al gate E2E: comprueba contratos que
pueden romperse en silencio durante una refactorización.

Qué se verifica y por qué
-------------------------
* IDs que el arranque de ``app.js`` necesita para montar la aplicación.
* Ausencia de recursos remotos: el servidor vive en LAN y puede no tener salida
  a Internet; una fuente o script en CDN dejaría la interfaz en blanco.
* Presencia de los endpoints que cada área consume, para que quitar una vista
  sin quitar su backend (o al revés) no pase inadvertido.
* Ausencia de datos operativos reales incrustados: rutas de NAS, IPs de
  campamento o datasets de demostración.
* Que la navegación se construya por permisos y no esté fija en el HTML.
"""

from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent
html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
css = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")


class IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.remote = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        for key in ("src", "href"):
            val = a.get(key)
            if val and (val.startswith("http://") or val.startswith("https://")):
                self.remote.append(val)


parser = IdParser()
parser.feed(html)

REQUIRED_IDS = {
    "setup", "setupForm", "login", "loginForm", "app", "content", "who", "logout", "title",
    # Contenedores de la navegación doble: menú por área y buscador transversal.
    "nav", "sidebar", "globalSearch", "globalSearchInput", "menuToggle", "eyebrow",
}
missing = sorted(REQUIRED_IDS - parser.ids)
if missing:
    raise SystemExit(f"Faltan IDs de UI: {missing}")
if parser.remote:
    raise SystemExit(f"Frontend depende de recursos remotos: {parser.remote}")

# Endpoints que la interfaz debe seguir consumiendo, agrupados por área para que
# el mensaje de error diga qué se rompió y no sólo que falta una cadena.
REQUIRED_API = {
    "núcleo": ["/api/setup/status", "/api/setup/first-admin", "/api/auth/login", "/api/me", "/api/health"],
    "vista resumen configurable": ["/api/dashboards", "/api/dev/widgets", "/api/dev/dashboards/"],
    "áreas y autoridad del dato": ["/api/me/context", "/api/areas", "/api/areas/authority", "/api/roles/"],
    "búsqueda y expedientes": ["/api/search", "/api/dossier/person/", "/api/dossier/asset/"],
    "RRHH": ["/api/persons", "/api/attendance", "/api/epp/requests", "/api/training/records", "/api/imports/"],
    "transporte": ["/api/transport/units", "/api/transport/checklists", "/api/transport/incidents"],
    "material y operación": ["/api/assets", "/api/node-operations", "/api/inventory/sessions",
                             "/api/evidence/repositories", "/api/evidence/register-existing", "/material-closeout"],
    "taller": ["/api/maintenance"],
    "administración": ["/api/roles", "/api/catalogs", "/api/asset-types", "/api/asset-technologies", "/api/audit"],
}
for area, endpoints in REQUIRED_API.items():
    absent = [e for e in endpoints if e not in js]
    if absent:
        raise SystemExit(f"Faltan contratos API de {area} en app.js: {absent}")

# Ningún dato operativo real puede quedar incrustado en el código publicado.
FORBIDDEN = ("const EMPLOYEES = [", "106 colaboradores", "Evidencias_Almagre_final_NO_MODIFICAR", "192.168.48.12")
for token in FORBIDDEN:
    if token in html or token in js:
        raise SystemExit(f"Se detectó dato/ruta operacional hardcodeada prohibida: {token}")

if 'minlength="10"' not in html:
    raise SystemExit("La UI inicial debe validar longitud mínima de contraseña")

# Los errores estructurados de FastAPI deben serializarse; si no, la interfaz
# vuelve a mostrar "[object Object]" al operador.
if "JSON.stringify(d)" not in js:
    raise SystemExit("La UI debe serializar errores estructurados en lugar de [object Object]")

# La navegación se construye desde los permisos del usuario. Si alguien volviera
# a fijar el menú en el HTML, las entradas reaparecerían para perfiles sin
# permiso y darían 403 al pulsarlas.
if "<button data-view=" in html:
    raise SystemExit("La navegación no debe estar fija en index.html: se construye por permisos en app.js")
for marker in ("const NAV = [", "function buildNav()", "if (!can(item.permission)) continue;"):
    if marker not in js:
        raise SystemExit(f"Falta el mecanismo de navegación por permisos: {marker}")

# Cada dominio debe tener su propia ficha. Una sola ficha universal fue un
# defecto explícito que esta versión corrige; que vuelva debe fallar el gate.
for renderer in ("async function person(", "async function node(", "async function asset(",
                 "async function transportUnit("):
    if renderer not in js:
        raise SystemExit(f"Falta el renderizador de ficha por dominio: {renderer}")

# La interfaz debe seguir siendo usable en tableta y teléfono.
if "@media (max-width: 860px)" not in css or "@media (max-width: 560px)" not in css:
    raise SystemExit("La hoja de estilo debe conservar los puntos de quiebre responsive")

print("FRONTEND_CONTRACT_OK")
