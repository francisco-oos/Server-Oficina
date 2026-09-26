# 33 · Guía de desarrollo · trabajo con varios programadores

Esta guía es el punto de entrada para quien recibe Server Oficina por primera
vez y va a modificarlo junto a otras personas.

## Regla número uno

> **No se crean proyectos paralelos.** Toda funcionalidad nueva entra en esta
> misma base, como módulo, y reutiliza Tracking Core. Un módulo que duplique
> personas, activos o eventos está mal diseñado, no importa lo cómodo que
> resulte.

## Puesta en marcha

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q          # 59 pruebas
.venv/bin/python run.py                # http://127.0.0.1:8080
```

Sin `SERVER_OFICINA_DATABASE_URL` se usa SQLite local. **PostgreSQL es la
fuente de verdad en despliegue**; SQLite sólo vale para desarrollo y pruebas.

Para el gate de navegador: `pip install -r requirements-e2e.txt` y
`./VALIDAR_FRONTEND_E2E.sh`.

## Estructura y responsabilidades

```
app/
  core/        configuración, seguridad, RBAC y áreas. Sin acceso a BD salvo security.
    config.py    variables de entorno → Settings
    security.py  hash de contraseñas, sesiones opacas, permisos efectivos
    rbac.py      catálogo de permisos técnicos y roles semilla
    areas.py     áreas y matriz de autoridad sobre el dato (declarativo)
  db/
    base.py      engine y sesión
    models.py    TODO el esquema. Un solo archivo a propósito: el modelo es el
                 contrato compartido y dispersarlo esconde las relaciones.
  services/    lógica de negocio reutilizable. No conoce FastAPI.
    bootstrap.py   siembra de permisos, roles y catálogos
    events.py      registro en el Tracking Core
    audit.py       registro auditable
    imports.py     preview/commit de importaciones
    lookup.py      búsqueda transversal y constructores de expediente
    widgets.py     registro de widgets de la vista resumen
    dashboards.py  composición y renderizado de vistas resumen
  api/         routers FastAPI. Validan, autorizan y delegan en services.
    deps.py        current_user / require(permiso)
    routes.py      núcleo heredado (RRHH, activos, nodos, taller, inventario…)
    routes_areas.py, routes_dashboard.py, routes_dossier.py, routes_transport.py
  static/      interfaz web
docs/          documentación técnica (español)
reports/       reportes de entrega de cada release
scripts/       instalación, gates, backup/restore, NAS
tests/         suite automática
```

**Dónde poner cada cosa**: si la lógica se puede describir sin mencionar HTTP,
va en `services/`. Si es validación de entrada, autorización o forma de la
respuesta, va en `api/`.

## Contratos que NO deben romperse

Romper cualquiera de éstos invalida la entrega:

1. **Persona ≠ contratación.** Una recontratación conserva `person_id`.
2. **Activo ≠ proyecto.** Serie, IMEI, QR e identidad sobreviven a transferencias.
3. **Estado actual ≠ historial.** Nunca se sobrescribe el pasado; una corrección
   es un evento nuevo.
4. **Ocurrió ≠ se registró.** Se conservan `occurred_at` y `recorded_at`.
5. **Predicción ≠ hecho.** SOH/RUL no provoca bajas automáticas.
6. **Evidencia ≠ sanción.** El área competente resuelve.
7. **Faltante de inventario ≠ pérdida definitiva.**
8. **Ningún campamento, ruta NAS ni IP hardcodeada.** Son datos configurables.
9. **Credenciales SMB fuera de PostgreSQL** (root-only en `/etc/server-oficina`).
10. **NAS fail-closed**: si el montaje desaparece, la carga se rechaza.
11. **`GET /api/health` debe seguir respondiendo 200** con la versión.
12. **La suite no escribe dentro del árbol de código** (ver doc 35).

Contratos de compatibilidad que conviene mantener salvo decisión explícita:
`GET /api/dashboard` (forma alpha.2/alpha.3), `GET /api/locate`, y los IDs de
UI que verifica `scripts/check-frontend-contract.py`.

## Cómo modificar el modelo de datos

El despliegue usa `Base.metadata.create_all` y **no hay herramienta de
migraciones**. De ahí la regla vigente desde alpha.3:

> **Sólo se AGREGAN tablas. No se añaden, renombran ni eliminan columnas de una
> tabla que ya tiene datos en producción.**

`create_all` crea tablas que faltan pero **no** altera tablas existentes: una
columna nueva existiría en el modelo y no en la base, y la aplicación fallaría
en cuanto la consultara.

Si necesita un dato nuevo sobre una entidad existente, hay tres salidas
legítimas:

| Situación | Solución |
|---|---|
| Atributo suelto, poco consultado | `metadata_json` de la entidad |
| Atributo con semántica propia | tabla satélite 1:1 (como `person_hr_profiles`) |
| Relación que cambia en el tiempo | tabla de periodos con `start`/`end` (como `transport_assignments`) |

Ejemplo real de esta versión: el área de un perfil se guardó en la tabla nueva
`role_areas` en vez de como columna de `roles`.

Si algún día hace falta una columna, la decisión debe promoverse a ADR
(`docs/03_DECISIONES_Y_RAZONAMIENTO.md`) junto con la adopción de una
herramienta de migración.

## Cómo crear un módulo nuevo

1. **Modelo**: tablas nuevas en `app/db/models.py`, en su propia sección
   comentada, con docstring que explique invariantes y por qué.
2. **Servicio**: lógica en `app/services/mi_modulo.py`, sin FastAPI.
3. **Permisos**: añadir los códigos a `PERMISSIONS` en `app/core/rbac.py` y
   repartirlos en `ROLE_MAP`.
4. **Autoridad**: declarar el dominio en `DATA_DOMAINS` (`app/core/areas.py`)
   diciendo quién es autoridad, quién consulta, quién propone y quién confirma.
5. **API**: `app/api/routes_mi_modulo.py` con su `APIRouter(prefix=...)`,
   registrado en `app/main.py`.
6. **Interfaz**: vista en `app/static/app.js`, registrada en `VIEWS` y en `NAV`.
7. **Widgets**: los indicadores del área, en `app/services/widgets.py` (doc 30).
8. **Pruebas**: un archivo `tests/test_<modulo>.py` que cubra el flujo feliz,
   los permisos y las reglas de negocio que el módulo introduce.
9. **Documentación**: actualizar `docs/00_INDICE_DOCUMENTACION.md` y la matriz
   de requisitos.

El dominio de Transporte de esta versión es el ejemplo completo de referencia:
`models.py` (3 tablas), `routes_transport.py`, `lookup.transport_dossier`,
3 widgets, vistas `transport` / `checklists` / `transportIncidents` /
`transportUnit`, y `tests/test_alpha4_transport.py`.

## Cómo integrar un área nueva

1. Añadir el `Area` a `AREAS` en `app/core/areas.py`.
2. Declarar sus dominios en `DATA_DOMAINS`.
3. Añadir su rol semilla a `ROLE_MAP` y a `DEFAULT_ROLE_AREAS`.
4. Registrar al menos un widget con esa `area` (la prueba
   `test_widget_registry_is_coherent` exige que ninguna área quede sin widgets).
5. Añadir su grupo a `AREA_LABELS` y sus entradas a `NAV` en `app/static/app.js`.

El dashboard del área se crea solo en el siguiente arranque.

## Cómo agregar un tipo de activo

**Sin tocar código**: Administración › Catálogos › Tipos de activo, o
`POST /api/asset-types`.

Lo que decide el comportamiento son las **capacidades**, nunca el nombre:

| Capacidad | Efecto |
|---|---|
| `node_field` | habilita operaciones de campo y abre la **ficha de nodo** |
| `transport` | habilita el dominio de Transporte y abre la **ficha de unidad** |
| `custody` | participa en custodia y entregas |
| `maintenance` | puede abrir órdenes de taller |
| `health` | admite observaciones SOH/RUL |
| `imei` | identificador IMEI relevante |

Registrar `PICKUP_4X4` con `["transport","custody","maintenance"]` lo convierte
en unidad de transporte sin desplegar nada
(`test_unit_must_declare_transport_capability`).

**Nunca** escribir `if type_code == "NODE"`. Usar siempre las capacidades.

## Cómo agregar eventos y estados

Todo por catálogo (`catalog_items`), sin desplegar:

| Catálogo | Para qué | Metadatos que interpreta el motor |
|---|---|---|
| `ASSET_STATUS` | estados de activo | `critical`, `transferable` |
| `ASSET_MOVEMENT` | movimientos | `status_after`, `opens_custody`, `closes_custody`, `requires_capability` |
| `NODE_OPERATION` | operaciones de campo | `movement_type` |
| `NODE_RESULT` | resultado por nodo | `status_after`, `movement_type` |
| `MAINTENANCE_STATUS` | flujo de taller | — |
| `ATTENDANCE_STATUS` | asistencia | — |
| `EMPLOYMENT_EVENT` | eventos laborales | `closes_engagement`, `final_status` |
| `LOCATION_TYPE` | tipos de ubicación | — |
| `ORGANIZATION_TYPE` | empresas / outsourcing | — |

Marcar un estado como `{"critical": true}` lo incorpora automáticamente a los
widgets de excepciones y al corte de material. Ése es el patrón: el motor lee
metadatos, no condicionales por cadena.

Un **evento del Tracking Core** se registra siempre con
`record_event(db, entity_type=…, entity_id=…, event_type=…, occurred_at=…,
source_type=…, actor_user_id=…, payload={…})`. `occurred_at` es obligatorio
conceptualmente: si no se conoce, se documenta por qué se usa la hora de
registro.

## Convenciones

- **Idioma**: código y API en inglés (`asset`, `movement`); comentarios,
  docstrings, documentación y textos de interfaz en **español profesional**.
- **Comentarios**: explican responsabilidades, decisiones, reglas de negocio,
  invariantes, efectos secundarios, seguridad y *por qué*. Nunca lo obvio
  (`# incrementamos i`).
- **Docstrings**: en todo módulo, y en clases y funciones con reglas no triviales.
- **Errores**: `HTTPException` con mensaje en español dirigido al operador.
  409 para conflicto de estado, 422 para dato inválido, 403 para permiso.
- **Permisos**: siempre `Depends(require("codigo.permiso"))`. Nunca comprobar
  el nombre de un rol en una ruta.
- **Fechas**: `datetime` con zona UTC. La interfaz localiza.

## Cómo ejecutar las pruebas

```bash
./VALIDAR_SERVER_OFICINA.sh   # todos los gates + manifiesto
./VALIDAR_BACKEND.sh          # sintaxis + 59 pruebas
./VALIDAR_FRONTEND.sh         # sintaxis JS + contrato de interfaz
./VALIDAR_DESPLIEGUE.sh       # sintaxis shell + contratos de despliegue
./VALIDAR_FRONTEND_E2E.sh     # recorrido de navegador (requiere Chromium)
```

Todos deben poder ejecutarse sobre una release instalada en modo **sólo
lectura**. Ver `docs/35_TESTING_Y_RUNTIME.md`.

## Cómo documentar un cambio

1. `CHANGELOG.md`, en la sección de la versión.
2. `docs/14_MATRIZ_REQUISITOS_Y_ESTADO.md`, con estado real y prueba que lo
   demuestra. **No marcar como implementado lo que esté parcial.**
3. El documento temático correspondiente.
4. Si es una decisión de arquitectura, ADR en `docs/03_DECISIONES_Y_RAZONAMIENTO.md`.

## Antes de entregar

- [ ] `./VALIDAR_SERVER_OFICINA.sh` en verde
- [ ] pruebas nuevas para la funcionalidad nueva
- [ ] ningún contrato de la lista anterior roto
- [ ] documentación y matriz actualizadas
- [ ] `./GENERAR_MANIFEST.sh` regenerado
- [ ] lo que quede parcial, declarado como parcial en los pendientes
