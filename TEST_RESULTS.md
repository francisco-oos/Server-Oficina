# Test Results · 0.1.0-alpha.3

Fecha de corte: 2026-09-11

## Resultado del paquete en entorno de construcción

La suite actual ejecuta **27 pruebas automáticas** y valida el mismo monorepo que se empaqueta.

```text
pytest -q
...........................                                              [100%]

BACKEND_OK
FRONTEND_CONTRACT_OK
FRONTEND_OK
DEPLOY_CONTRACT_OK
DEPLOY_OK
```

Cobertura principal de backend:

- bootstrap/login/sesiones/RBAC;
- creación de perfiles personalizados, edición de permisos y asignación a usuarios;
- protección de perfiles base y del último administrador;
- persona estable, altas, bajas, renuncia, despido y recontratación conservando `person_id`;
- categoría, licencia/vigencia, rotación, supervisor, proyecto, grupo, ubicación y unidad;
- asistencia manual e importada;
- cursos, EPP y casos sin resolución automática de RRHH;
- organizaciones/outsourcing normalizados;
- Asset Core: NODE, RADIO, ANTENNA, PHONE, COMPUTER, DRONE, VEHICLE, SERVER y NAS;
- identificadores serie/IMEI/QR/número económico y búsqueda por identificador;
- tipos, tecnologías, estados y movimientos futuros agregables sin modificar lógica específica;
- custodia, asignación, transferencia y localizador persona/activo;
- Tracking Nodes por lote: TENDIDO → ROTACION → LEVANTADO → RETORNO;
- excepciones DAMAGED/BURNED/MISSING/LOST/STOLEN/SEIZED/MAINTENANCE/HIBERNATED/NO_INFO;
- recuperación y deshibernación;
- taller/mantenimiento, piezas retiradas/instaladas, downtime y salud/RUL no autoritativa;
- inventario físico, faltantes observados y conciliación;
- carga masiva CSV de activos preservando columnas informativas como metadatos;
- cierre auditable de material por proyecto y transferencia posterior sin reescribir el snapshot;
- evidencias LOCAL/SMB, fail-closed, upload SHA-256, indexación de archivos ya existentes sin moverlos;
- prevención de traversal fuera del repositorio de evidencias;
- historia de aceptación transversal RRHH + material + nodos + taller + inventario + cierre.

## Validaciones estáticas/contratos

```text
python3 -m compileall -q app tests run.py
node --check app/static/app.js
./VALIDAR_FRONTEND.sh
./VALIDAR_DESPLIEGUE.sh
```

Resultado:

```text
FRONTEND_CONTRACT_OK
FRONTEND_OK
DEPLOY_CONTRACT_OK
DEPLOY_OK
```

El contrato frontend verifica, entre otras cosas, que no existan rutas históricas/IP de campamento hardcodeadas ni datasets demo incrustados y que estén presentes los endpoints/vistas operativos de alpha.3.

## Smoke HTTP real aislado

Se levantó Uvicorn con una base SQLite temporal aislada y se verificó:

```text
GET /api/health        -> 200, version=0.1.0-alpha.3
GET /api/setup/status  -> 200, needs_setup=true
GET /                  -> 200
GET /static/app.js     -> 200
GET /static/styles.css -> 200
SMOKE_OK
```

## Gate E2E de navegador

`VALIDAR_FRONTEND_E2E.sh` incluye un recorrido reproducible:

```text
primer admin → login → dashboard → alta de persona → alta de nodo → TENDIDO → logout
```

En **este entorno de construcción**, Chromium está administrado con `URLBlocklist=["*"]`. La política bloquea localhost antes de cargar la aplicación, por lo que el runner devuelve explícitamente:

```text
E2E_BLOCKED: Chromium tiene una política administrada URLBlocklist=*; ejecute este gate en la Latitude/QA host
```

No se transforma ese bloqueo en un PASS ficticio. El gate queda preparado para ejecutarse en la Latitude instalada.

## Evidencia física ya validada en la Latitude para la baseline alpha.2

Durante la preparación e instalación real del servidor se comprobó:

- Debian 13/Xfce, SSH y UFW operativos;
- suspensión/hibernación bloqueadas y pulsación corta de power ignorada;
- Docker Engine/containerd sobreviven reboot y usan `/srv/docker`;
- PostgreSQL 18.6 en contenedor `healthy`;
- persistencia PostgreSQL tras restart;
- `pg_dump -Fc` y `pg_restore` a base temporal;
- instalación versionada de alpha.2, `server-oficina.service`, timer de backup y acceso LAN;
- primer administrador creado desde navegador.

## Gates físicos pendientes para alpha.3

La release sigue siendo **alpha** hasta cerrar en la Latitude/NAS real:

- actualización `alpha.2 → alpha.3` con backup pre-upgrade;
- `/api/health` y rollback controlado de release;
- E2E de navegador en la Latitude;
- repositorio SMB/NAS real y credenciales fuera de PostgreSQL;
- importación de archivos reales de Oficina/Material;
- pruebas multiusuario por perfiles reales;
- backup integral + restore integral después de operar alpha.3;
- estabilidad prolongada y revisión visual del usuario.
