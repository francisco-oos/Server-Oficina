# 14 · Matriz de requisitos y estado real

Estado de cada requisito del encargo frente a lo que el sistema **hace de
verdad**, con la prueba que lo demuestra y los archivos donde vive.

Leyenda: **OK** implementado y probado · **PARCIAL** funciona con límite
declarado · **PENDIENTE** no implementado.

> Nada se marca OK por estar documentado. Todo OK tiene una prueba automática o
> un gate que lo respalda.

## 1 · Concepto central: Tracking Core común, experiencia por dominio

| Requisito | Estado | Prueba | Archivos |
|---|---|---|---|
| Tracking Core común (identidad, proyecto, ubicación, relación temporal, responsable, custodia, evento, estado derivado, evidencia, procedencia, auditoría, `occurred_at`/`recorded_at`) | OK | `test_temporal.py`, `test_alpha3_operational.py` | `app/db/models.py`, `app/services/events.py` |
| La ficha de cada dominio NO es intercambiable | OK | `test_dossier_structures_differ_per_domain` | `app/services/lookup.py`, `app/static/app.js` |
| Gate que impide volver a una ficha universal | OK | `scripts/check-frontend-contract.py` | idem |

## 2 · Seguimiento de personas

| Requisito | Estado | Prueba | Archivos |
|---|---|---|---|
| Identidad estable `person_id` separada de la contratación | OK | `test_person_dossier_keeps_identity_across_rehire` | `models.py`, `lookup.person_dossier` |
| Altas, bajas, recontrataciones con IDs laborales distintos | OK | idem, `test_admin_and_lifecycle.py` | `routes.py` |
| Outsourcing / empresa normalizada + `provider` histórico | OK | `test_alpha3_operational.py` | `Organization`, `EngagementOrganizationLink` |
| Contratos y renovaciones | OK | `test_alpha3_operational.py` | `ContractPeriod` |
| Proyecto, grupo/cuadrilla, supervisor, ubicación, unidad | OK | `test_person_summary_exposes_localisation_block` | `PersonAssignment` |
| Asistencia (manual e importada) | OK | `test_alpha3_operational.py`, `test_training_cases_imports.py` | `AttendanceRecord` |
| Rotación trabajo/descanso | PARCIAL | `test_person_summary_exposes_localisation_block` | se **captura y muestra** (`rotation_on_days`/`off_days`); **no** genera calendario ni proyecta descansos |
| Categoría, licencia y vigencia | OK | idem | `PersonHRProfile` |
| Cursos | OK | `test_training_cases_imports.py` | `TrainingRecord` |
| EPP | OK | `test_alpha3_operational.py` | `EppRequest`, `EppHistory` |
| Radios y otros activos entregados | OK | `test_dossier_structures_differ_per_domain` | `assets_current`, `assets_history` |
| Incidencias / HSE | OK | `test_training_cases_imports.py` | `CaseRecord` |
| Nodos perdidos/dañados relacionados | OK | `test_node_dossier_shows_operational_cycle_not_just_status` | `node_exceptions` |
| Devoluciones | OK | `test_alpha3_operational.py` | `AssetCustody.end_at` |
| Evidencias e historial completo | OK | `test_alpha3_operational.py` | `EvidenceRecord`, `OperationalEvent` |
| Observaciones libres sobre la persona | PARCIAL | — | hay `metadata_json` en `PersonHRProfile` y notas en casos; **no** hay bitácora de observaciones con su propia UI |
| **Localizar personal** y ver Estado / Grupo / Responsable / Unidad / Conductor / Radio / Teléfono / Ubicación / Proyecto | OK | `test_person_summary_exposes_localisation_block`, E2E | `lookup.person_summary`, `GET /api/dossier/person/{id}/summary` |
| Abrir el expediente completo desde el resultado | OK | E2E `ui_smoke.py` | `app/static/app.js` |

## 3 · Seguimiento de nodos

| Requisito | Estado | Prueba | Archivos |
|---|---|---|---|
| Eventos TENDIDO, PLANTADO, ROTACIÓN, LEVANTADO, RETORNO | OK | `test_node_lifecycle_catalog_covers_every_required_event` | catálogos `NODE_OPERATION` / `ASSET_MOVEMENT` |
| DAÑADO, QUEMADO, NO ENCONTRADO, EXTRAVIADO, ROBADO, INCAUTADO, MANTENIMIENTO, HIBERNANDO, ALMACENADO, RETORNO SIN INFORMACIÓN | OK | idem | catálogos `ASSET_STATUS` / `NODE_RESULT` |
| El nodo NO se reduce a un campo `estado` | OK | `test_node_dossier_shows_operational_cycle_not_just_status` | `lookup.node_dossier` |
| Estado actual mostrado **junto a su derivación** | OK | idem | `current_state.derived_from` |
| Identidad, tipo, fabricante, tecnología, serie, QR, lote, operación, proyecto, ubicación | OK | idem | `_asset_header`, `NodeOperation` |
| Quién lo tenía o manejaba | OK | idem | `responsible`, `participants`, custodia |
| Movimientos, excepciones, fechas, incidencias | OK | idem | `AssetMovement`, `NodeOperationItem` |
| Taller / reparaciones, inventarios, evidencias, historial | OK | `test_alpha3_operational.py` | ficha de nodo |
| Responde dónde estuvo, qué ocurrió, quién intervino y su situación | OK | E2E + `test_node_dossier_...` | — |

## 4 · Otros activos y material

| Requisito | Estado | Prueba | Archivos |
|---|---|---|---|
| Asset Core compartido sin Tracking Nodes obligatorio | OK | `test_dossier_structures_differ_per_domain` | capacidades de `AssetType` |
| Identidad, número económico, serie, IMEI, QR, tipo | OK | `test_cross_search_finds_every_identifier...` | `AssetIdentifier` |
| Proyecto, ubicación, almacén, custodia | OK | `test_alpha3_operational.py` | `AssetCustody` |
| Entregas, transferencias, devoluciones | OK | idem | `AssetMovement` |
| Inventarios, mantenimiento, reparación | OK | idem | `InventoryCount`, `MaintenanceOrder` |
| Pérdida, robo, extravío, baja | OK | idem | catálogo `ASSET_STATUS` |
| Evidencia | OK | idem | `EvidenceRecord` |
| Patrón visual común **adaptado** al tipo de activo | OK | `check-frontend-contract.py` | `app/static/app.js` |

## 5 · Transporte

| Requisito | Estado | Prueba | Archivos |
|---|---|---|---|
| Transporte con dominio propio, no inventario genérico | OK | `test_alpha4_transport.py` | `routes_transport.py` |
| Unidad, conductor, asignaciones | OK | `test_assignment_closes_previous_without_overwriting_history` | `TransportAssignment` |
| Teléfono y radio asociados, sin duplicar registros | OK | `test_unit_links_radio_and_phone_from_asset_core` | idem |
| Proyecto, grupo, disponibilidad | OK | idem | idem |
| Checklist | OK | `test_checklist_with_failure_does_not_immobilize_unit` | `TransportChecklist` |
| Incidencias | OK | `test_incident_reported_by_any_area_resolved_by_transport` | `TransportIncident` |
| Mantenimiento e historial | OK | `test_incident_link_to_workshop_order_is_validated` | `MaintenanceOrder` |
| Fotografías del checklist | PARCIAL | — | se pueden adjuntar como **evidencias** del activo; **no** hay captura de foto integrada en el formulario de checklist |
| Vínculo persona ↔ unidad ↔ conductor ↔ grupo aprovechable desde otras áreas | OK | `test_person_summary_exposes_localisation_block` | `lookup.person_summary` |

## 6 · Taller / TX / mantenimiento

| Requisito | Estado | Prueba | Archivos |
|---|---|---|---|
| Recepción, orden, diagnóstico, pruebas, reparación | OK | `test_alpha3_operational.py` | `MaintenanceOrder`, catálogo `MAINTENANCE_STATUS` |
| Piezas, serial retirado, serial instalado | OK | idem | `MaintenancePart` |
| Resultado, no reparable, hibernando, almacenado | OK | idem + `test_node_lifecycle_catalog...` | catálogos |
| Downtime | OK | idem | `downtime_minutes` |
| Evidencias | OK | idem | `EvidenceRecord` |
| Evento de taller ≠ movimiento de custodia | OK | `test_dossier_structures_differ_per_domain` | secciones separadas en la ficha |
| «Entregado» como estado de salida de taller | PARCIAL | — | se representa con `MAINTENANCE_OUT` + custodia; **no** hay un acuse de entrega firmado |

## 7 · Autoridad por área

| Requisito | Estado | Prueba | Archivos |
|---|---|---|---|
| Matriz autoridad / consulta / propuesta / confirmación | OK | `test_authority_matrix_is_declared_for_every_domain` | `app/core/areas.py` |
| RRHH: identidad, contrataciones, asignaciones, asistencia, EPP | OK | `test_alpha3_operational.py` | `DATA_DOMAINS` |
| HSE: cursos, cumplimiento, incidencias | OK | `test_training_cases_imports.py` | idem |
| Transporte: unidades, conductores, checklist | OK | `test_incident_reported_by_any_area_resolved_by_transport` | idem |
| Material: inventario, custodia, existencia | OK | `test_alpha3_operational.py` | idem |
| Operación: historia de nodos · Taller: diagnóstico | OK | idem | idem |
| Proponer ≠ confirmar | OK | `test_incident_reported_by_any_area_resolved_by_transport` | permisos separados |
| No aislar departamentos: consulta compartida | OK | `test_areas_and_role_area_assignment` | `GET /api/areas/authority` |
| RBAC evolucionado para reflejarlo | OK | `test_alpha4_areas_and_dashboard.py` | `rbac.py` (37 permisos, 8 roles), `role_areas` |

## 8 · Revisión completa de la interfaz

| Requisito | Estado | Prueba | Archivos |
|---|---|---|---|
| Navegación, jerarquía, agrupación por áreas | OK | contrato + E2E | `NAV`, `buildNav()` |
| Dashboards, formularios, tablas, fichas, búsquedas | OK | E2E `ui_smoke.py` | `app/static/app.js` |
| Timeline/historial, estado actual, relaciones, evidencia | OK | idem | fichas por dominio |
| Acciones contextuales y permisos | OK | idem | `can()` + backend |
| Responsive | OK | E2E a 390 px sin desbordamiento | `styles.css` |
| Densidad, legibilidad, flujos cotidianos | OK | E2E + revisión | `styles.css`, `reports/REPORTE_CAMBIOS_UI.md` |
| Evitar que todo sea tabla CRUD | OK | contrato de interfaz | resumen/ficha/timeline/alertas |
| Pensada para oficina y campo | OK | E2E responsive | — |

## 9 · Dashboard configurable en modo DEV

| Requisito | Estado | Prueba | Archivos |
|---|---|---|---|
| Widgets disponibles (registro) | OK | `test_widget_registry_is_coherent` | `app/services/widgets.py` (28 widgets) |
| Cuáles aparecen, orden, posición, tamaño, título | OK | `test_dev_can_show_hide_reorder_and_retitle` | `dashboard_widget_placements` |
| Área, métrica/fuente | OK | idem | declarados por widget |
| Permisos requeridos | OK | `test_dashboard_render_filters_widgets_by_permission` | `effective_placements` |
| Visibilidad por perfil/rol | OK | `test_placement_role_restriction_narrows_only` | `role_names` |
| Dashboard general | OK | `test_dashboards_are_seeded_per_area` | `GENERAL_SEED` |
| Dashboards por departamento | OK | idem | uno por área |
| Interfaz DEV: MOSTRAR / OCULTAR / ORDENAR / CONFIGURAR / ASIGNAR | OK | E2E `ui_smoke.py` | vista `devDashboard` |
| Agregar widgets sin reescribir el dashboard | OK | `test_widget_registry_is_coherent` | decorador `@widget` |
| Documentado cómo crear widgets | OK | — | `docs/30_...md` |
| La configuración no se pisa al reiniciar | OK | `test_seed_does_not_overwrite_administrator_configuration` | `ensure_dashboards` |
| Un widget roto no tumba la vista | OK | `test_widget_failure_is_isolated` | `widgets.resolve` |
| Arrastrar y soltar para reordenar | PARCIAL | — | se reordena con botones ▲▼, que funcionan con guantes; **no** hay drag & drop |

## 10 · Navegación por áreas + transversal

| Requisito | Estado | Prueba | Archivos |
|---|---|---|---|
| Trabajar desde el área propia | OK | E2E | `buildNav()`, dashboards por área |
| Búsqueda transversal (persona, nodo, radio, teléfono, unidad, activo, IMEI, QR, serie, económico) | OK | `test_cross_search_finds_every_identifier_and_routes_to_the_right_dossier` | `lookup.search` |
| Dirigir a la ficha adecuada | OK | idem + E2E | campo `dossier` |
| NO una ficha universal | OK | `test_dossier_structures_differ_per_domain` | 4 constructores distintos |
| No ofrecer lo que no se puede abrir, pero avisar | OK | `test_search_hides_results_the_user_cannot_open` | `hidden_by_permissions` |

## 11 · Experiencia de vista resumen

| Requisito | Estado | Prueba | Archivos |
|---|---|---|---|
| ¿Qué está pasando? | OK | `test_dashboards_are_seeded_per_area` | widgets de métrica |
| ¿Qué requiere atención? | OK | idem | widgets de excepción |
| ¿Qué cambió? | OK | idem | altas/bajas/actividad reciente |
| ¿Qué está pendiente? | OK | idem | EPP, cursos, órdenes, inventarios |
| ¿Qué debo atender yo? | OK | idem | widget `general_mis_pendientes`, filtrado por permisos |
| No sólo contadores: métricas, pendientes, alertas, cambios, accesos rápidos | OK | E2E | 4 tipos de widget + enlaces |
| Respeta perfil y área | OK | `test_dashboard_render_filters_widgets_by_permission` | — |

## 12 · Documentación

| Requisito | Estado | Archivo |
|---|---|---|
| Arquitectura general | OK | `02_ARQUITECTURA.md` |
| Tracking Core | OK | `27_TRACKING_CORE.md` |
| Modelo de dominio | OK | `28_MODELO_DOMINIO_POR_AREA.md` |
| Autoridad de datos por área | OK | `29_AUTORIDAD_DATO_POR_AREA.md` |
| Arquitectura de UI y navegación | OK | `31_ARQUITECTURA_UI_Y_NAVEGACION.md` |
| Dashboard configurable y registro de widgets | OK | `30_DASHBOARD_CONFIGURABLE_Y_WIDGETS.md` |
| RBAC | OK | `22_RBAC_PERFILES_CONFIGURABLES.md`, `29_...md` |
| API | OK | `32_API_REFERENCIA.md` |
| Modelo de datos | OK | `06_MODELO_DATOS.md`, `28_...md` |
| Cómo crear módulo / widget / área / tipo de activo / evento | OK | `33_...md`, `30_...md` |
| Importaciones | OK | `09_...md`, `34_CONTRATO_INGESTA_DOCUMENTAL.md` |
| Testing | OK | `35_TESTING_Y_RUNTIME.md` |
| Deployment | OK | `07_INSTALACION_DEBIAN.md`, `24_...md` |
| Backup / restore | OK | `36_BACKUP_RESTORE.md` |
| Onboarding de desarrolladores | OK | `33_GUIA_DESARROLLO_MULTIDESARROLLADOR.md` |
| Matriz de estado real | OK | este documento |

## 13 · Comentarios y docstrings en español

| Requisito | Estado | Evidencia |
|---|---|---|
| Comentarios profesionales en español, sin trivialidades | OK | `reports/REPORTE_POST.md` |
| Docstrings en módulos, clases y funciones relevantes | OK | todo `app/`, `tests/`, `scripts/` |
| Reglas destacadas (persona ≠ contratación, etc.) documentadas en el código | OK | `areas.py`, `models.py`, `lookup.py`, `widgets.py` |

## 14 · Trabajo multidesarrollador

| Requisito | Estado | Archivo |
|---|---|---|
| Estructura, responsabilidades, convenciones | OK | `33_...md` |
| Cómo añadir funcionalidad y ejecutar pruebas | OK | `33_...md`, `35_...md` |
| Contratos que no deben romperse | OK | `33_...md` |
| Cómo modificar modelos (regla aditiva) | OK | `33_...md` |
| Contratos para Ingesta Documental | OK | `34_...md` |

## 15 · Reglas que no se rompen

| Regla | Estado | Prueba |
|---|---|---|
| Persona ≠ contratación; recontratación conserva `person_id` | OK | `test_person_dossier_keeps_identity_across_rehire` |
| Activo ≠ proyecto; identidad sobrevive a transferencias | OK | `test_alpha3_operational.py` |
| Estado actual ≠ historial | OK | `test_node_dossier_shows_operational_cycle_not_just_status` |
| Ocurrió ≠ se registró | OK | `test_temporal.py`, `test_checklist_with_failure...` |
| Predicción ≠ hecho (SOH/RUL) | OK | `test_alpha3_operational.py` |
| Evidencia ≠ sanción | OK | `test_training_cases_imports.py` |
| Faltante de inventario ≠ pérdida definitiva | OK | `test_alpha3_operational.py` |
| No hardcodear campamentos | OK | `check-frontend-contract.py` |
| Credenciales fuera de PostgreSQL | OK | gate de despliegue |
| NAS fail-closed | OK | `test_alpha3_operational.py` |
| No crear otro proyecto | OK | misma base, sólo tablas añadidas |

## 16 · Pruebas y correcciones

| Requisito | Estado | Evidencia |
|---|---|---|
| Suite completa ejecutada | OK | 60 pruebas · `reports/REPORTE_POST.md` |
| Regresiones corregidas | OK | 0 regresiones; 27 pruebas heredadas intactas |
| Pruebas para las funciones nuevas | OK | 33 pruebas nuevas |
| Backend, contratos y permisos | OK | gates + pruebas de 403 |
| Frontend | OK | contrato + E2E de navegador |
| Dashboard configurable | OK | 13 pruebas |
| Distintos roles | OK | 6 perfiles distintos ejercitados |
| Fichas y timelines | OK | `test_alpha4_dossiers_and_search.py` + E2E |
| Deployment y `/api/health` | OK | `VALIDAR_DESPLIEGUE.sh`, smoke HTTP |
| **`PermissionError` en validación manual sobre release instalada** | OK | `test_runtime_paths.py` + verificación con árbol sólo lectura y usuario sin privilegios |

## 17 · Revisión independiente final

Ver `reports/REPORTE_REVISION_INDEPENDIENTE.md`.

## 18 · Entrega

Ver `reports/` (PRE, POST, cambios de interfaz, pruebas, seguridad, pendientes)
y `MANIFEST.sha256`.
