# Test Results · 0.1.0-alpha.2

Fecha de corte: 2026-09-11

## Resultado del paquete en entorno de construcción

```text
./scripts/verify-package.sh
...........                                                              [100%]
BACKEND_OK
FRONTEND_CONTRACT_OK
FRONTEND_OK
DEPLOY_CONTRACT_OK
DEPLOY_OK
PACKAGE_OK
```

Cobertura del gate base:

- `pytest`: **11 passed**;
- `compileall` de `app`, `tests` y `run.py`: OK;
- sintaxis `app/static/app.js` con Node: OK;
- contrato frontend: IDs/endpoints requeridos, sin CDN y sin dataset demo incrustado: OK;
- sintaxis de scripts/iniciadores: OK;
- contrato de despliegue PostgreSQL 18.6 + localhost 5432 + `/srv`: OK.

## Smoke real de proceso alpha.2

Se levantó Uvicorn con SQLite temporal aislado en `127.0.0.1:18080` y se ejecutó `scripts/smoke.sh`.

```text
GET /api/health       -> 200, version=0.1.0-alpha.2
GET /api/setup/status -> 200, needs_setup=true
GET /                 -> 200
GET /static/app.js    -> 200
GET /static/styles.css-> 200
SMOKE_OK
```

## Gate E2E de navegador

Se añadió un recorrido Playwright reproducible (`VALIDAR_FRONTEND_E2E.sh`) para configuración inicial → login → dashboard → alta de persona → detalle → logout.

En **este entorno de construcción**, Chromium tiene una política administrada global `URLBlocklist=*`, por lo que la navegación a localhost es bloqueada por el navegador antes de que la aplicación pueda cargarse. El runner detecta la condición y devuelve de forma explícita:

```text
E2E_BLOCKED: Chromium tiene una política administrada URLBlocklist=*; ejecute este gate en la Latitude/QA host
```

Por tanto, el E2E visual queda como gate físico y **no se declara PASS** en esta construcción.

## Evidencia ya validada en la Latitude durante la preparación del host

Esta evidencia proviene de la sesión de preparación física del servidor y no sustituye instalar alpha.2:

- Debian 13/Xfce y SSH operativos;
- UFW activo;
- suspensión/hibernación bloqueadas y pulsación corta de power ignorada;
- Docker Engine/containerd sobreviven reboot y usan `/srv/docker`;
- PostgreSQL 18.6 en contenedor `healthy`;
- datos PostgreSQL persisten tras restart;
- `pg_dump -Fc` creado;
- `pg_restore` a una base temporal realizado correctamente;
- base `server_oficina` quedó limpia después de retirar el esquema experimental paralelo.

## Gates físicos que siguen pendientes para alpha.2

- `INSTALAR_EN_TABLETA.sh` completo sobre la release empaquetada;
- app `server-oficina.service` después de reboot;
- primer admin real desde navegador;
- acceso LAN PC + teléfono;
- `VALIDAR_FRONTEND_E2E.sh` en host sin política bloqueante;
- archivo real de Oficina: preview/commit controlado;
- roles HR/HSE/Supervisor con usuarios reales de prueba;
- backup integral app+BD + restore integral de la release instalada;
- estabilidad 24 h.

La release conserva la clasificación **alpha** hasta cerrar esos gates.
