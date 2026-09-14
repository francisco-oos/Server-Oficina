# Reporte PRE · estado recibido (0.1.0-alpha.3)

Estado del paquete **tal como se recibió**, antes de cualquier modificación.

## Verificación de procedencia

El ZIP entregado (`Server-Oficina-0.1.0-alpha.3.zip`) se extrajo íntegramente y
se comparó archivo por archivo contra el árbol del repositorio:

```
diff -rq zipsrc/server-oficina-0.1.0-alpha.3 <repo> --exclude=.git
→ sin diferencias
```

Se trabajó sobre **esa misma base**. No se creó ningún proyecto paralelo.

## Suite de pruebas PRE

```
pytest -q
...........................                                          [100%]
27 passed
```

| Gate | Resultado PRE |
|---|---|
| `VALIDAR_BACKEND.sh` | PASS (27 pruebas + compileall) |
| `VALIDAR_FRONTEND.sh` | PASS (sintaxis JS + contrato) |
| `VALIDAR_DESPLIEGUE.sh` | PASS (sintaxis shell + contratos) |
| `VALIDAR_FRONTEND_E2E.sh` | no ejecutable: recorrido escrito contra la UI anterior |

## Inventario del código recibido

| Componente | Tamaño | Observación |
|---|---:|---|
| `app/api/routes.py` | 1 502 líneas | todas las rutas en un solo archivo |
| `app/db/models.py` | 599 líneas | 46 tablas |
| `app/static/app.js` | 170 líneas | 18 vistas comprimidas en una línea cada una |
| `app/static/index.html` | 67 líneas | navegación fija en HTML |
| `app/static/styles.css` | ~230 líneas | sin puntos de quiebre responsive |
| `docs/` | 27 documentos | |
| `tests/` | 27 pruebas | |

## Estado real por funcionalidad (no por documentación)

Verificado leyendo el código, no el `CHANGELOG`.

### Backend sólido

RRHH operativo, Asset Core con identificadores múltiples, Tracking Nodes por
lote, taller con piezas y downtime, inventario con faltantes, cierre de proyecto
con snapshot, evidencias LOCAL/SMB con SHA-256 y fail-closed, RBAC configurable
y catálogos editables: **implementados y probados**.

### Diferencias entre lo que el sistema pretende y lo que la interfaz presentaba

| # | Hallazgo | Severidad |
|---|---|---|
| 1 | **Dashboard hardcodeado.** `GET /api/dashboard` devolvía 7 contadores fijos. Añadir una tarjeta exigía tocar endpoint, JSON y plantilla. No existía configuración, ni modo DEV, ni registro de widgets. | Alta — requisito 9 ausente por completo |
| 2 | **Sin dominio de Transporte.** Un vehículo era un activo más; no había conductor, asignación, checklist ni incidencias. El vínculo persona ↔ unidad ↔ conductor ↔ grupo no era consultable. | Alta — requisito 5 ausente |
| 3 | **Navegación no departamental.** El menú agrupaba en Operación / Oficina / Administración, no por área. RRHH, Transporte, Material y Taller no tenían punto de entrada propio. | Alta — requisito 10 parcial |
| 4 | **Ficha de persona insuficiente.** `personDetail` apilaba tablas. No existía el bloque de localización (Estado / Grupo / Responsable / Unidad / Conductor / Radio / Teléfono / Ubicación / Proyecto) que pide el encargo. | Alta — requisito 2 parcial |
| 5 | **Ficha de nodo inexistente.** Un nodo se mostraba con la misma plantilla que un radio: estado, movimientos y poco más. No había ciclo operacional, ni excepciones destacadas, ni derivación del estado actual. | Alta — requisito 3 parcial |
| 6 | **Sin modelo de autoridad por área.** El RBAC decía qué operación se podía ejecutar, pero nada expresaba quién es autoridad, quién consulta, quién propone y quién confirma. | Alta — requisito 7 ausente |
| 7 | **Búsqueda transversal limitada.** `/api/locate` devolvía personas y activos en un mismo saco, sin indicar qué ficha abrir ni por qué coincidió, y sin filtrar por permisos. | Media — requisito 10 parcial |
| 8 | **Predominio de tablas CRUD.** Casi toda vista era formulario + tabla. Poco resumen, poca ficha, timeline mínimo, sin alertas ni acciones contextuales. | Media — requisito 8 |
| 9 | **Sin diseño responsive.** Ningún `@media`. La barra lateral fija de 250 px hacía la aplicación inutilizable en tableta vertical y teléfono, pese a ser una herramienta de campo. | Media — requisito 8 |
| 10 | **`app.js` ilegible.** 170 líneas con vistas completas de 3 000 caracteres en una sola línea. Inviable para varios programadores. | Media — requisito 14 |
| 11 | **Catálogo de nodos incompleto.** Faltaban `PLANTADO` y `ALMACENADO`, ambos listados explícitamente en el encargo. | Baja |
| 12 | **Menú no filtrado por permisos.** Las entradas se mostraban a todos y fallaban con 403 al pulsarlas. | Baja |

### Defecto de validación reproducido

`VALIDAR_SERVER_OFICINA.sh` ejecutado a mano contra una release instalada en
modo sólo lectura, con un usuario sin privilegios:

```
PermissionError: [Errno 13] Permission denied: '<release>/tests/runtime'
```

Reproducido de forma controlada en este entorno. Causa raíz: `tests/conftest.py`
fijaba la base SQLite y `SERVER_OFICINA_DATA_DIR` **dentro del árbol de código**,
y `app/core/config.py` crea el `data_dir` en tiempo de importación, por lo que
fallaba antes de recolectar una sola prueba. Había cuatro escrituras al árbol:
`tests/runtime/`, `tests/test.db`, `.pytest_cache/` y `__pycache__/`.

### Defecto de empaquetado

Los `*.sh` estaban versionados con modo `100644`. Ejecutar
`./VALIDAR_SERVER_OFICINA.sh` desde un clon del repositorio devolvía
`Permission denied`. El ZIP sí conservaba el bit de ejecución, de modo que el
defecto sólo aparecía por la vía del repositorio.

## Conclusión PRE

La base de datos y la lógica de negocio estaban en buen estado. La brecha
principal estaba **entre el modelo de dominio y lo que la interfaz presentaba**,
más los tres requisitos nuevos ausentes (dashboard configurable, Transporte y
autoridad por área) y el defecto de validación sobre release instalada.
