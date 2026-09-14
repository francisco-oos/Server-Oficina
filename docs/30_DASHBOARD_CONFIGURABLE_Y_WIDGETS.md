# 30 · Vista resumen configurable y registro de widgets

## El problema que resuelve

Hasta alpha.3 el dashboard era una función que devolvía siete contadores fijos.
Agregar una tarjeta obligaba a tocar el endpoint, el JSON de respuesta y la
plantilla. Las tarjetas estaban **hardcodeadas**.

## La separación

| Qué | Dónde | Quién lo cambia |
|---|---|---|
| Qué widgets **existen** | `app/services/widgets.py` (código versionado) | un programador |
| Qué widgets **se muestran**, orden, tamaño, título, a quién | `dashboard_definitions` + `dashboard_widget_placements` (BD) | un administrador, desde el modo DEV |

Un administrador puede MOSTRAR, OCULTAR, ORDENAR, CONFIGURAR y ASIGNAR A
PERFIL/ÁREA sin que nadie toque código.

## Vistas resumen semilla

Se crean al arrancar: una general (`general`) y una por área (`rrhh`, `hse`,
`transporte`, `material`, `operacion`, `taller`). Un administrador puede crear
otras con `POST /api/dev/dashboards`.

## Regla de siembra (importante al actualizar)

La siembra coloca widgets **sólo la primera vez** que se crea un dashboard. Si
una release posterior agrega widgets nuevos, aparecen en el catálogo DEV pero
**no** se auto-insertan en dashboards existentes: reaparecer solas sería
sobrescribir una decisión explícita del administrador.

Verificado por `test_seed_does_not_overwrite_administrator_configuration`.

## Seguridad: la configuración acota, nunca amplía

Cada widget declara el permiso que exige. El renderizado descarta, en orden:

1. colocaciones ocultas por el administrador;
2. colocaciones cuyo `widget_key` ya no existe (release que lo retiró) — se
   ignoran en vez de romper el dashboard;
3. **widgets cuyo permiso el usuario no posee**;
4. widgets restringidos a perfiles a los que el usuario no pertenece.

El punto 3 es la garantía: colocar un widget en el dashboard de alguien **no**
le concede visibilidad sobre datos que su permiso niega.
Verificado por `test_dashboard_render_filters_widgets_by_permission` y
`test_placement_role_restriction_narrows_only`.

## Aislamiento de fallos

Un resolver que lance una excepción devuelve `{"ok": false, "error": ...}` para
esa tarjeta; el resto de la vista se dibuja con normalidad y el detalle técnico
va al log del servicio, no a la pantalla del operador.
Verificado por `test_widget_failure_is_isolated`.

## Cómo crear un widget nuevo

Sólo hay que escribir una función decorada. **No** se toca el endpoint, ni la
interfaz, ni la base de datos, ni hay migración.

```python
# app/services/widgets.py
@widget(
    key="material_sin_custodia",              # único y estable; es la clave guardada
    title="Activos sin custodia",             # título por defecto (el DEV puede sobreescribirlo)
    area="MATERIAL",                          # debe existir en app/core/areas.py
    kind=KIND_METRIC,                         # METRIC | LIST | BREAKDOWN | ALERT
    permission="assets.view",                 # debe existir en app/core/rbac.py
    description="Activos vigentes sin responsable asignado.",
    default_size="SMALL",                     # SMALL | MEDIUM | LARGE | FULL
    default_position=70,
    answers=("¿Qué requiere atención?",),
)
def _material_sin_custodia(db, ctx):
    total = db.scalar(
        select(func.count()).select_from(Asset)
        .where(Asset.active.is_(True), Asset.custodian_person_id.is_(None))
    ) or 0
    return metric(total, hint="sin responsable", tone=TONE_WARN if total else TONE_OK,
                  link=_link("assets"))
```

Al reiniciar el servicio aparece en **Administración › Modo DEV · Dashboard**,
listo para colocarse donde se quiera.

### Contrato del resolver

`resolver(db: Session, ctx: WidgetContext) -> dict`

`ctx` trae `user`, `permissions` (frozenset), `area_codes` y `options` (el JSON
que el administrador configuró para esa colocación concreta).

Constructores de payload disponibles, según el `kind`:

| kind | constructor | forma |
|---|---|---|
| `KIND_METRIC` | `metric(valor, hint=, tone=, link=)` | número grande |
| `KIND_LIST` / `KIND_ALERT` | `listing([{primary, secondary, meta, tone, link}], empty=)` | lista corta |
| `KIND_BREAKDOWN` | `breakdown([{label, value, tone}], empty=)` | desglose |

`tone` ∈ `neutral` · `ok` · `warn` · `bad`. `link` se construye con
`_link("vista", id=...)`; la interfaz lo traduce a una de sus vistas en
`widgetLink()` (`app/static/app.js`). Si la vista no está en ese mapa, la
tarjeta simplemente no será navegable — no se rompe.

### Reglas al escribir un resolver

- **Nunca** filtrar por un literal de estado o de tipo. Usar el catálogo
  (`_critical_status_codes`) o las capacidades del tipo (`_node_type_ids`), para
  que un estado o una tecnología nueva se incorporen sin tocar código.
- Devolver siempre una forma válida aunque no haya datos: `listing([])` con su
  `empty`, nunca `None`.
- Consultar, no escribir. Un widget no debe tener efectos secundarios.
- Declarar el permiso **más restrictivo** que el dato exige.

### Checklist

1. Función decorada en `app/services/widgets.py`.
2. `test_widget_registry_is_coherent` valida permiso, área, tamaño y descripción.
3. Si debe salir por defecto en el dashboard general, agregarlo a `GENERAL_SEED`
   en `app/services/dashboards.py` (sólo afecta instalaciones nuevas).
4. Documentarlo si introduce una regla de negocio no evidente.

## Catálogo actual

28 widgets: 6 RRHH, 3 HSE, 3 Transporte, 6 Material, 6 Operación, 3 Taller y 1
transversal (**Qué debo atender**, que filtra pendientes por lo que el usuario
realmente puede resolver).

## API

| Método | Ruta | Permiso | Para qué |
|---|---|---|---|
| `GET` | `/api/dashboards` | `dashboard.view` | vistas disponibles |
| `GET` | `/api/dashboards/{key}` | `dashboard.view` | vista renderizada y filtrada |
| `GET` | `/api/dev/widgets` | `dashboard.configure` | catálogo de widgets |
| `GET` | `/api/dev/dashboards/{key}` | `dashboard.configure` | composición cruda (incluye lo oculto) |
| `PUT` | `/api/dev/dashboards/{key}` | `dashboard.configure` | guardar composición completa |
| `POST` | `/api/dev/dashboards` | `dashboard.configure` | crear vista |
| `PATCH` | `/api/dev/dashboards/{key}` | `dashboard.configure` | renombrar / activar / desactivar |
| `DELETE` | `/api/dev/dashboards/{key}` | `dashboard.configure` | eliminar (sólo las no-sistema) |

El `PUT` sustituye la composición **en bloque**: la configuración es un
documento ordenado y una validación fallida no debe dejar media composición
aplicada. Rechaza widgets desconocidos, repetidos, tamaños inválidos y perfiles
inexistentes (`test_dev_layout_validation_rejects_bad_input`).

## Compatibilidad

`GET /api/dashboard` (alpha.2/alpha.3) sigue existiendo sin cambios. Hay
instalaciones y pruebas que dependen de su forma.
