# Reporte de pruebas · 0.1.0-alpha.4

Fecha de corte: 2026-09-14

## Suite automática

```
pytest -q
..............................................................  [100%]
62 passed
```

| Archivo | Pruebas | Cubre |
|---|---:|---|
| `test_core.py` | 3 | bootstrap, login, sesiones, RBAC |
| `test_temporal.py` | 1 | `occurred_at` ≠ `recorded_at` |
| `test_admin_and_lifecycle.py` | 3 | usuarios, ciclo laboral |
| `test_training_cases_imports.py` | 4 | cursos, casos, importaciones preview/commit |
| `test_alpha3_operational.py` | 15 | Asset Core, nodos, taller, inventario, evidencias, cierre |
| `test_alpha3_acceptance_story.py` | 1 | historia transversal de aceptación |
| `test_alpha4_areas_and_dashboard.py` | 13 | áreas, autoridad, vista resumen configurable, modo DEV |
| `test_alpha4_transport.py` | 7 | dominio de Transporte |
| `test_alpha4_dossiers_and_search.py` | 10 | expedientes por dominio y búsqueda transversal |
| `test_runtime_paths.py` | 5 | aislamiento del runtime de pruebas |
| **Total** | **62** | 27 heredadas + 35 nuevas |

**0 regresiones.** Las 27 pruebas heredadas de alpha.3 pasan sin que se haya
modificado ninguna de sus aserciones.

## Qué protege cada prueba nueva

### Reglas de dominio

| Prueba | Regla protegida |
|---|---|
| `test_person_dossier_keeps_identity_across_rehire` | persona ≠ contratación |
| `test_node_dossier_shows_operational_cycle_not_just_status` | estado actual ≠ historial |
| `test_assignment_closes_previous_without_overwriting_history` | no se sobrescribe el pasado |
| `test_checklist_with_failure_does_not_immobilize_unit` | evidencia ≠ sanción |
| `test_incident_reported_by_any_area_resolved_by_transport` | proponer ≠ confirmar |
| `test_dossier_structures_differ_per_domain` | **Core común ≠ interfaz común** |
| `test_node_lifecycle_catalog_covers_every_required_event` | los 15 eventos de nodo son configuración, no código |
| `test_radio_is_resolved_by_capability_not_by_type_name` | capacidades, no nombres de tipo |

### Seguridad

| Prueba | Garantía |
|---|---|
| `test_dashboard_render_filters_widgets_by_permission` | la configuración no otorga visibilidad |
| `test_placement_role_restriction_narrows_only` | la restricción por perfil sólo acota |
| `test_search_hides_results_the_user_cannot_open` | la búsqueda no ofrece lo que daría 403 |
| `test_asset_dossier_requires_the_permission_of_its_domain` | cada ficha exige el permiso de su dominio |
| `test_transport_permissions_are_enforced` | 403 en todo el dominio de Transporte |

### Robustez

| Prueba | Garantía |
|---|---|
| `test_widget_failure_is_isolated` | un widget roto no tumba la vista resumen |
| `test_orphan_placement_does_not_break_rendering` | un widget retirado por una release no rompe nada |
| `test_dev_layout_validation_rejects_bad_input` | una validación fallida no deja media configuración |
| `test_seed_does_not_overwrite_administrator_configuration` | actualizar no pisa lo configurado |
| `test_seeded_asset_types_gain_new_capabilities_on_upgrade` | actualizar sí incorpora capacidades nuevas |
| `test_incident_link_to_workshop_order_is_validated` | no se enlaza una orden de otro activo |

### Runtime

`test_runtime_paths.py` (5) fija que la base, el `data_dir` y la caché queden
**fuera** del árbol de código.

## Gate E2E de navegador — EJECUTADO

```
FRONTEND_E2E_OK
```

A diferencia de alpha.3, donde quedó bloqueado por política de Chromium, **este
gate se ejecutó realmente**. Recorrido verificado en navegador:

1. primer administrador desde cero
2. inicio de sesión
3. vista resumen general con sus widgets y los 7 dashboards disponibles
4. navegación agrupada por área (RRHH, Transporte, Taller visibles)
5. cambio a la vista resumen de Transporte
6. alta de persona → apertura automática de su expediente
7. presencia de los 8 campos del bloque de localización
8. pestañas propias de persona (Historia laboral, Asistencia)
9. alta de nodo → apertura de la **ficha de nodo**, no de la genérica
10. registro de TENDIDO
11. situación actual mostrando `DEPLOYED` y la línea `L-E2E` derivadas del historial
12. alta de unidad → apertura de la **ficha de unidad**
13. asignación de conductor y verificación en la flota
14. búsqueda transversal por ID laboral → encuentra la persona
15. búsqueda por QR → encuentra el nodo, indica que coincidió por QR y abre su ficha
16. modo DEV: renombrar un widget, ocultar otro, guardar
17. verificación de que el operador ve el cambio en su vista resumen
18. responsive a 390 px: botón de menú, cierre automático al navegar, **sin desbordamiento horizontal**
19. cierre de sesión

Se vigilan además los errores de consola de JavaScript: cualquier excepción hace
fallar el gate. **Ninguna registrada.**

## Verificación del `PermissionError`

Reproducido y corregido con el escenario real.

**Antes:**
```
PermissionError: [Errno 13] Permission denied: '<release>/tests/runtime'
```

**Después**, con el árbol en `chmod -R a-w` y un usuario sin privilegios:
```
62 passed
archivos escritos dentro del árbol de código: 0
```

## Validaciones estáticas

```
python3 scripts/syntax-check.py app tests run.py   → SYNTAX_OK
node --check app/static/app.js                     → OK
python3 scripts/check-frontend-contract.py         → FRONTEND_CONTRACT_OK
bash -n (todos los scripts)                        → DEPLOY_OK
pyflakes app/ tests/ scripts/ run.py               → sin hallazgos
```

## Gates completos

```
BACKEND_OK
FRONTEND_CONTRACT_OK
FRONTEND_OK
DEPLOY_CONTRACT_OK
DEPLOY_OK
FRONTEND_E2E_OK
```

## Lo que estas pruebas NO demuestran

- Que la aplicación funcione sobre **PostgreSQL** (la suite corre en SQLite).
  El gate de despliegue verifica el contrato, no la ejecución.
- Que la actualización sobre la instalación real de la Latitude funcione.
- Que los formatos reales de la oficina importen sin ajustes.
- Comportamiento bajo concurrencia física ni con NAS real.

Ver `reports/PENDIENTES_REALES.md`.
