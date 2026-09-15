# HANDOFF R00 — Baseline y ejecución local

## Base autoritativa

Repositorio: `francisco-oos/Server-Oficina`

Baseline inspeccionada:

```text
e21d82ef7feb8020b3bd03612a97a3d879c7a99f
Server-Oficina-0.1.0-alpha.3
```

## Estado verificado antes de este relevo

La alpha.3 incorpora código real, no sólo documentación:

- Asset Core;
- Tracking Nodes;
- mantenimiento/taller;
- inventario;
- evidencias LOCAL/SMB;
- RBAC configurable;
- relaciones laborales y recontratación;
- cierre auditable de proyecto.

El repositorio declara 27 pruebas automáticas.

## Hallazgos pendientes confirmados

1. El Dashboard sigue definido de forma rígida en frontend.
2. No existe todavía un modo desarrollador para elegir widgets, posición y alcance del resumen.
3. La navegación no está completamente gobernada por permisos desde la UI.
4. El localizador devuelve IDs útiles desde backend, pero la presentación no resuelve suficientemente nombres/contexto operacional.
5. La UI todavía no refleja con suficiente claridad la semántica diferente de cada área.
6. Comentarios profesionales en español son parciales; `routes.py`, `models.py` y `app.js` necesitan refactor/documentación.
7. Transporte/HSE especializado continúan incompletos.
8. Los gates físicos de alpha.3 no se han cerrado todavía.

## Objetivo de R00

Separar el entorno de desarrollo de la instalación de producción y permitir probar Server Oficina en Windows con SQLite local.

R00 NO modifica todavía dominio ni esquema.

## Archivos aportados por este relevo

- `PREPARAR_LOCAL_WINDOWS.ps1`
- `INICIAR_LOCAL_WINDOWS.ps1`
- `VALIDAR_LOCAL_WINDOWS.ps1`
- `DETENER_LOCAL_WINDOWS.ps1`
- `docs/PROTOCOLO_RELEVOS.md`
- este handoff

## Ejecución esperada

Desde PowerShell, dentro del repositorio:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\PREPARAR_LOCAL_WINDOWS.ps1
.\VALIDAR_LOCAL_WINDOWS.ps1
.\INICIAR_LOCAL_WINDOWS.ps1
```

La ejecución local usa:

```text
SERVER_OFICINA_ENV=development
SERVER_OFICINA_DATABASE_URL=sqlite+pysqlite:///./runtime/local/server_oficina.db
SERVER_OFICINA_DATA_DIR=./runtime/local
SERVER_OFICINA_HOST=127.0.0.1
SERVER_OFICINA_PORT=8080
```

No toca PostgreSQL, Docker ni `/srv/server-oficina`.

## Gate para R01

R01 no debe comenzar cambios del Dashboard hasta confirmar:

- entorno virtual creado;
- dependencias instaladas;
- baseline pytest conocida;
- compileall PASS;
- `node --check` PASS si Node está disponible;
- aplicación local responde `/api/health`;
- navegador abre la UI.

## Objetivo previsto de R01

Dashboard/Modo Dev:

- configuración persistente de widgets;
- orden visible configurable;
- alcance global / perfil / usuario según diseño final;
- navegación filtrada por permisos;
- sin romper RBAC de backend;
- pruebas nuevas para configuración y seguridad.
