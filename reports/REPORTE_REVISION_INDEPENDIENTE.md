# Reporte de revisión independiente final

> **Addendum OpenAI R1 (2026-09-14):** una segunda revisión posterior encontró
> casos no cubiertos por esta pasada. Ver
> `reports/REPORTE_REVISION_OPENAI_R1.md`. La conclusión de este documento no
> debe interpretarse como ausencia absoluta de defectos.

Segunda pasada sobre Server Oficina **como si fuera otro ingeniero que lo recibe
por primera vez**, incluida la deuda técnica creada por esta misma evolución.

## Defectos encontrados y corregidos

### 1 · Decisiones tomadas por nombre de tipo en lugar de por capacidad — CORREGIDO

**Gravedad: alta.** Es exactamente la regla que el propio sistema impone, rota
por el código nuevo.

Tres sitios decidían comportamiento comparando el **código** del tipo de activo:

```python
if atype.code == "RADIO":          # app/services/lookup.py
```
```javascript
assets.filter(x => x.type_code === 'RADIO')    // app/static/app.js
assets.filter(x => x.type_code === 'PHONE')
```

Consecuencia: registrar `RADIO_SATELITAL` —algo que la interfaz permite sin
desplegar nada— habría dejado ese equipo invisible para el resumen de
localización y para el selector de radio de una unidad.

**Corrección**: se declararon las capacidades `radio` y `phone` en las semillas
y los tres sitios pasaron a filtrar por capacidad.

**Efecto secundario detectado al corregir**: `ensure_operational_catalogs` sólo
creaba tipos ausentes; nunca actualizaba los existentes. Una instalación ya
desplegada habría quedado con `RADIO` sin la capacidad nueva y la corrección no
habría surtido efecto al actualizar. Se cambió a una **unión** de capacidades
que añade las que el producto declara y conserva las que agregó el operador.

Cubierto por `test_radio_is_resolved_by_capability_not_by_type_name` y
`test_seeded_asset_types_gain_new_capabilities_on_upgrade`.

### 2 · Endpoints huérfanos sin interfaz — CORREGIDO

`POST /api/dev/dashboards`, `PATCH /api/dev/dashboards/{key}` y
`DELETE /api/dev/dashboards/{key}` existían y estaban probados, pero el modo DEV
no ofrecía ninguna forma de usarlos: funciones sin camino desde la interfaz.

Se añadieron al configurador el formulario de creación de vistas resumen, el
botón de activar/desactivar para las del sistema y el de eliminar para las
creadas por un administrador —este último con confirmación explícita.

### 3 · Importaciones sin usar y código muerto — CORREGIDO

`pyflakes` reportaba 22 importaciones sin usar, algunas heredadas de alpha.3
(`shutil` en `routes.py`) y otras introducidas por esta evolución. Todas
eliminadas; el análisis estático queda limpio.

### 4 · Petición innecesaria en cada carga — CORREGIDO

La vista de Activos pedía `/api/locations` y no usaba el resultado. Eliminada.

### 5 · Conductores ambiguos en el selector — CORREGIDO

El selector de conductor mostraba sólo el nombre. Dos personas pueden llamarse
igual y asignar la unidad equivocada es un error caro. Ahora muestra nombre + ID
laboral, como el resto de selectores de persona.

### 6 · Construcción de URLs sin codificar — CORREGIDO

Trece llamadas construían rutas interpolando identificadores directamente. Los
valores provienen de la propia API y no había vector real de inyección, pero se
endurecieron con `encodeURIComponent` por robustez.

### 7 · Scripts sin bit de ejecución — CORREGIDO

Heredado de alpha.3: los `*.sh` estaban versionados como `100644`. Ejecutar
`./VALIDAR_SERVER_OFICINA.sh` desde un clon devolvía `Permission denied`. El ZIP
sí conservaba el bit, así que el defecto sólo se manifestaba por la vía del
repositorio. Corregido con `git update-index --chmod=+x`.

### 8 · Catálogo de nodos incompleto — CORREGIDO

Faltaban `PLANTADO` y `ALMACENADO`, ambos listados explícitamente en el encargo.
Añadidos como semillas y cubiertos por
`test_node_lifecycle_catalog_covers_every_required_event`.

### 9 · El recorrido E2E no se ejecutaba — CORREGIDO

El runner sólo buscaba Chromium en rutas del sistema. Ahora también busca bajo
`PLAYWRIGHT_BROWSERS_PATH`, y el gate **se ejecuta de verdad** en lugar de
reportarse como bloqueado.

## Revisado y encontrado correcto

| Aspecto | Verificación |
|---|---|
| **XSS** | toda interpolación que llega al DOM pasa por `esc()`; revisadas las 40 excepciones aparentes, todas son números internos o texto que se escapa aguas abajo |
| **Inyección SQL** | SQLAlchemy con parámetros ligados en todas las consultas nuevas |
| **Escalada de privilegios** | la configuración del dashboard sólo puede acotar; probado explícitamente |
| **Estados imposibles** | resolver una incidencia ya resuelta → 409; cerrar un inventario cerrado → 409; enlazar una orden de otro activo → 422 |
| **Datos duplicados** | Transporte referencia activos existentes; no hay tabla paralela de vehículos, radios ni teléfonos |
| **Acciones peligrosas** | cierre de proyecto, cierre de inventario y borrado de vista resumen piden confirmación explicando qué hacen y qué no |
| **Permisos** | cada endpoint nuevo exige permiso; probados los 403 de transporte, fichas, búsqueda y modo DEV |
| **Responsive** | verificado en navegador a 390 px |
| **Documentación** | índice reescrito; la matriz de requisitos distingue OK de PARCIAL con la prueba que lo respalda |

## Deuda técnica conocida y declarada

No se corrigieron por estar fuera del alcance razonable de esta entrega, y se
declaran en lugar de ocultarse:

| Deuda | Riesgo | Nota |
|---|---|---|
| `app/api/routes.py` conserva 1 490 líneas y el estilo comprimido de alpha.3 | medio | los módulos nuevos sí están separados por dominio; partirlo ahora habría mezclado refactorización masiva con cambio funcional en la misma entrega |
| No hay herramienta de migraciones | medio | mitigado por la regla «sólo se agregan tablas», documentada y respetada; hará falta antes de necesitar alterar una columna |
| La suite comparte un `TestClient` y una base | bajo | deliberado; obliga a usar identificadores propios por prueba, y así está documentado |
| Las consultas de expediente hacen varios `db.get()` en bucle | bajo | correcto para los volúmenes de una cuadrilla; conviene revisar si un proyecto supera algunos miles de activos |
| Sin paginación en listados | bajo | hay límites duros (100–300 filas); con inventarios grandes hará falta paginar |

## Conclusión

No se detectó ninguna incoherencia entre lo que la documentación afirma y lo que
el código hace. Lo que quedó parcial está marcado como parcial en
`docs/14_MATRIZ_REQUISITOS_Y_ESTADO.md`, y los gates físicos que faltan están en
`reports/PENDIENTES_REALES.md`.
