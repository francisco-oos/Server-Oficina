# Reporte POST · entrega 0.1.0-alpha.4

Resultado tras la revisión, corrección y evolución de la misma base alpha.3.

## Resumen

| Métrica | PRE | POST |
|---|---:|---:|
| Pruebas automáticas | 27 | **62** |
| Regresiones | — | **0** |
| Tablas | 46 | 52 (6 nuevas, ninguna modificada) |
| Permisos RBAC | 34 | 37 |
| Roles semilla | 7 | 8 |
| Widgets de dashboard | 0 (7 contadores fijos) | **28 configurables** |
| Vistas resumen | 1 hardcodeada | **7 configurables** (general + 6 áreas) |
| Vistas de interfaz | 18 | 28 |
| Fichas por dominio | 2 genéricas | **4 específicas** |
| `app/static/app.js` | 170 líneas ilegibles | 2 450 líneas comentadas |
| Puntos de quiebre responsive | 0 | 3 |
| Documentos técnicos | 27 | 37 |

## Gates

```
BACKEND_OK              62 pruebas + verificación sintáctica sin escritura
FRONTEND_CONTRACT_OK    contrato estructural de interfaz
FRONTEND_OK             sintaxis JavaScript
DEPLOY_CONTRACT_OK      PostgreSQL 18.6, /srv, backup pre-upgrade, rollback
DEPLOY_OK               sintaxis de todos los scripts
FRONTEND_E2E_OK         recorrido completo de navegador  ← ejecutado de verdad
```

**El gate E2E de navegador pasó realmente en este entorno**, a diferencia de
alpha.3 donde quedó bloqueado por política de Chromium. Recorrido verificado:

```
primer admin → login → vista resumen (7 dashboards) → alta de persona →
expediente con bloque de localización → alta de nodo → ficha de nodo →
TENDIDO → estado derivado del historial → alta de unidad →
asignación de conductor → ficha de unidad → búsqueda por ID laboral →
búsqueda por QR → apertura de la ficha correcta → modo DEV (renombrar y
ocultar widgets, guardar) → verificación del cambio en la vista del operador →
responsive a 390 px sin desbordamiento → logout
```

Se vigilan además los errores de consola: una excepción de JavaScript hace
fallar el gate.

## Lo que se corrigió

### 1 · `PermissionError` en validación manual sobre release instalada

Corregido y **verificado reproduciendo el escenario real**: árbol en modo sólo
lectura (`chmod -R a-w`) y usuario sin privilegios.

```
62 passed
artefactos escritos dentro del árbol de código: 0
```

Sin `chmod -R 777` y sin debilitar permisos de `/opt`. Ver
`docs/35_TESTING_Y_RUNTIME.md`. Fijado por `tests/test_runtime_paths.py`.

### 2 · Vista resumen configurable en modo DEV

Registro de 28 widgets en código (`app/services/widgets.py`) separado de la
configuración en base de datos. MOSTRAR, OCULTAR, ORDENAR, REDIMENSIONAR,
RETITULAR y ASIGNAR A PERFIL, más creación de vistas por departamento.

Garantías probadas: la configuración **acota pero nunca amplía** privilegios; un
widget roto no tumba la pantalla; la siembra de arranque no pisa lo configurado;
una colocación huérfana se ignora en vez de romper.

### 3 · Dominio de Transporte

Tres tablas nuevas, ocho endpoints, cuatro vistas y tres widgets. La unidad, el
radio y el teléfono **son** activos del Asset Core: no se duplican registros.
Reasignar cierra la asignación anterior con fecha.

### 4 · Autoridad sobre el dato por área

15 dominios de información con autoridad, consulta, propuesta y confirmación
declaradas. Materializado en permisos: reportar una incidencia de unidad exige
`cases.create` (cualquier área), resolverla exige `transport.manage` (sólo
Transporte).

### 5 · Interfaz reconstruida

Navegación doble (por área + transversal), cuatro fichas específicas por
dominio, vista resumen que responde las cinco preguntas del encargo, y diseño
responsive real.

### 6 · Catálogo de nodos completado

Añadidos `PLANTADO` y `ALMACENADO`/`STORED`, que faltaban. Los 15 eventos del
apartado 3 están ahora cubiertos y verificados por prueba.

## Hallazgos de la revisión independiente sobre el propio trabajo

Ver `reports/REPORTE_REVISION_INDEPENDIENTE.md`. Se corrigieron tres defectos
introducidos por esta misma evolución, entre ellos dos decisiones tomadas por
**nombre de tipo** en lugar de por capacidad —justo la regla que el sistema
impone— y dos endpoints huérfanos sin interfaz.

## Comentarios y docstrings

Todo el código nuevo y el tocado lleva documentación en español profesional,
centrada en responsabilidades, decisiones de arquitectura, reglas de negocio,
invariantes, efectos secundarios y seguridad. No hay comentarios triviales.

Reglas explicadas en el punto donde se aplican:

| Regla | Dónde está comentada |
|---|---|
| persona ≠ contratación | `lookup.person_dossier`, `models.EmploymentEngagement` |
| activo ≠ proyecto | `lookup.asset_dossier`, `28_MODELO_DOMINIO_POR_AREA.md` |
| estado actual ≠ historial | `lookup.node_dossier`, `models.TransportAssignment` |
| ocurrió ≠ se registró | `models.TransportChecklist`, `widgets._actividad_reciente` |
| predicción ≠ hecho | `lookup._asset_health`, `app.js healthSection` |
| evidencia ≠ sanción | `areas.DATA_DOMAINS`, `routes_transport.add_checklist` |
| faltante ≠ pérdida | `widgets._material_faltantes`, `app.js inventorySection` |

## Compatibilidad con el despliegue de la Latitude

- **Sólo se agregaron tablas.** Ninguna tabla existente cambió de forma, así que
  `Base.metadata.create_all` promueve la instalación sin migración manual.
- `GET /api/health` intacto; verificado por smoke HTTP y por el gate de despliegue.
- `GET /api/dashboard` y `GET /api/locate` conservados para compatibilidad.
- PostgreSQL 18.6, `/srv`, backup pre-upgrade y rollback de release: sin cambios.
- Los 27 casos de prueba heredados pasan **sin modificación de sus aserciones**.

## Gates físicos que siguen pendientes

Esta release sigue siendo **alpha**. Ver `reports/PENDIENTES_REALES.md`.
