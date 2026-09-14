# Test Results · 0.1.0-alpha.1

Fecha de ejecución: 2026-09-10/11 UTC (sesión de construcción)

## Suite

```text
pytest
..........                                                               [100%]
11 passed in 0.92s
```

```text
python3 -m compileall -q app tests run.py
COMPILE_OK
```

```text
node --check app/static/app.js
bash -n scripts/*.sh
STATIC_AND_SCRIPTS_OK
```

## Smoke real de proceso

Se levantó Uvicorn sobre SQLite aislado y se consultaron endpoints HTTP:

```text
SMOKE_OK 0.1.0-alpha.1
GET /api/health -> 200 OK
GET /            -> 200 OK
```

## Casos cubiertos

- health;
- bootstrap admin de un solo uso;
- creación de usuario con rol;
- identidad estable persona/rehire con nuevo ID;
- baja y recontratación por API;
- EPP: supervisor solicita pero no valida;
- EPP: HR/Admin valida y crea historial oficial;
- importación XLSX PREVIEW→COMMIT + SHA;
- capacitación RRHH→HSE;
- caso abierto sin sanción automática + resolución humana;
- reporte tardío: `occurred_at` separado de `recorded_at`.

## Limitación del entorno

El entorno de construcción no tuvo resolución DNS para `pip`; las pruebas usaron FastAPI, SQLAlchemy, openpyxl, pytest, httpx y Uvicorn ya disponibles. `psycopg` no estaba instalado. Por ello PostgreSQL y el instalador Debian quedan como **gate físico obligatorio** en la Latitude.
