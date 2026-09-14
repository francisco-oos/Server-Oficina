# Test Results · 0.1.0-alpha.4

Fecha de corte: 2026-09-14

El detalle completo está en `reports/REPORTE_PRUEBAS.md`. Este archivo es el
resumen de la ficha de release.

## Resultado

```text
pytest -q
..............................................................  [100%]
62 passed

BACKEND_OK
FRONTEND_CONTRACT_OK
FRONTEND_OK
DEPLOY_CONTRACT_OK
DEPLOY_OK
FRONTEND_E2E_OK
```

**62 pruebas** (27 heredadas de alpha.3 sin modificar + 35 nuevas).
**0 regresiones.**

## Cobertura de backend

Además de todo lo que ya cubría alpha.3 —bootstrap, RBAC, perfiles
configurables, identidad estable y recontratación, asistencia, cursos, EPP,
casos, organizaciones, Asset Core, Tracking Nodes con sus excepciones, taller,
salud/RUL, inventario, carga masiva, evidencias LOCAL/SMB y cierre de
proyecto—, esta versión añade:

- registro de widgets coherente con RBAC y con las áreas;
- siembra de 7 vistas resumen (general + una por área);
- **la configuración del dashboard no puede otorgar visibilidad** que el permiso niega;
- restricción por perfil que sólo acota;
- mostrar, ocultar, ordenar, redimensionar y retitular widgets;
- validación que rechaza widget desconocido, repetido, tamaño inválido y perfil inexistente **sin dejar media configuración aplicada**;
- la siembra de arranque no pisa lo que configuró el administrador;
- una colocación huérfana no rompe el renderizado;
- un widget que falla se aísla y el resto de la vista sigue funcionando;
- matriz de autoridad declarada para los 15 dominios;
- área de perfil asignable, que no otorga permisos;
- unidad de transporte verificada por **capacidad** del tipo, no por su nombre;
- reasignación que cierra la anterior sin sobrescribir el historial;
- radio y teléfono referenciados del Asset Core, sin duplicar registros;
- checklist con falla que **no** inmoviliza la unidad;
- incidencia que cualquier área reporta y sólo Transporte resuelve (403 verificado);
- enlace a orden de taller validado contra el mismo activo;
- expediente que conserva `person_id` a través de una recontratación;
- bloque de localización con los 9 campos del encargo;
- ficha de nodo con ciclo operacional y estado derivado de su historial;
- **las cuatro fichas tienen estructuras distintas** (prueba que impide volver a una ficha universal);
- búsqueda transversal por nombre, ID laboral, serie, IMEI, QR y número económico;
- la búsqueda oculta lo que el usuario no podría abrir e informa cuánto ocultó;
- los 15 eventos de nodo existen como catálogo configurable;
- resolución por capacidad y no por nombre de tipo, incluso tras actualizar;
- aislamiento del runtime de pruebas respecto al árbol de código.

## Gate E2E de navegador — EJECUTADO

A diferencia de alpha.3, donde quedó bloqueado por política de Chromium, **este
gate se ejecutó de verdad**:

```text
primer admin → login → vista resumen (7 dashboards) → alta de persona →
expediente con bloque de localización → alta de nodo → ficha de nodo →
TENDIDO → estado derivado del historial → alta de unidad →
asignación de conductor → ficha de unidad → búsqueda por ID laboral →
búsqueda por QR → apertura de la ficha correcta → modo DEV (renombrar,
ocultar, guardar) → verificación del cambio en la vista del operador →
responsive a 390 px sin desbordamiento → logout
```

Los errores de consola de JavaScript hacen fallar el gate. Ninguno registrado.

## Validación sobre release instalada en sólo lectura

El `PermissionError` reportado está corregido y verificado reproduciendo el
escenario real: árbol en `chmod -R a-w` y usuario sin privilegios.

```text
62 passed
archivos escritos dentro del árbol de código: 0
```

Sin `chmod -R 777` y sin debilitar permisos de `/opt`.

## Validaciones estáticas

```text
python3 scripts/syntax-check.py app tests run.py   → SYNTAX_OK
node --check app/static/app.js                     → OK
python3 scripts/check-frontend-contract.py         → FRONTEND_CONTRACT_OK
pyflakes app/ tests/ scripts/ run.py               → sin hallazgos
```

El contrato de interfaz verifica además que la navegación se construya por
permisos, que exista un renderizador de ficha por dominio, que no haya recursos
remotos ni rutas de campamento incrustadas, y que se conserven los puntos de
quiebre responsive.

## Smoke HTTP aislado

```text
GET /api/health        -> 200, version=0.1.0-alpha.4
GET /api/setup/status  -> 200, needs_setup=true
GET /                  -> 200
GET /static/app.js     -> 200
GET /static/styles.css -> 200
```

## Gates físicos pendientes

La release sigue siendo **alpha**. Lo que falta cerrar en la Latitude real está
en `reports/PENDIENTES_REALES.md`: actualización alpha.3 → alpha.4, rollback,
E2E en el hardware real, NAS SMB real, archivos reales de oficina, pruebas
multiusuario, respaldo y restauración completos, estabilidad prolongada y la
revisión visual del usuario.
