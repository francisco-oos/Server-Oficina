# 06 · Modelo de datos vigente — 0.1.0-alpha.3

## Identidad y acceso

`users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `session_tokens`.

Roles de negocio son configurables; permisos técnicos son contratos versionados. Las sesiones son opacas/revocables y la BD conserva el hash del token.

## RRHH / organización

- `persons`: identidad humana estable;
- `employment_engagements`: alta/recontratación e ID laboral del periodo;
- `contract_periods`: renovaciones;
- `organizations` + `engagement_organization_links`: empresa/outsourcing/contratista normalizados sin eliminar compatibilidad con `provider` legado;
- `person_hr_profiles`: categoría, licencia/vigencia, rotación y datos operativos;
- `projects`, `work_groups`, `group_assignments`, `locations`, `person_assignments`;
- `attendance_records`, `employment_lifecycle_events`;
- EPP, capacitación, casos/evidencia heredados.

## Asset Core

- `asset_types`: tipo configurable + capacidades;
- `asset_technologies`: tecnología/fabricante configurable;
- `assets`: identidad permanente + snapshot actual;
- `asset_identifiers`: serie/IMEI/QR/económico/otros;
- `asset_custody`: periodos de custodia;
- `asset_movements`: historia autoritativa de movimientos.

## Tracking Nodes

- `node_operations`: operación/lote;
- `node_operation_items`: equipo individual, estacas, resultado, responsable y estados antes/después.

El nombre del tipo no habilita Tracking Nodes; lo habilita la capacidad `node_field`.

## Taller / condición

- `maintenance_orders`;
- `maintenance_parts`;
- `asset_health_observations`.

Una observación de salud/RUL no ejecuta una transición de estado.

## Inventario y cierre de proyecto

- `inventory_sessions` + `inventory_counts`: conteo físico y faltantes observados;
- `project_closeouts`: snapshot auditable al cierre del proyecto; no mueve material automáticamente.

## Evidencias

- `evidence_repositories`: LOCAL/SMB, mount y URI canónica;
- `evidence_records`: relación, ruta relativa, SHA-256, tamaño, MIME, procedencia y fechas.

Un archivo existente en NAS puede indexarse sin moverlo. Las credenciales SMB no forman parte del modelo de negocio.

## Trazabilidad transversal

`operational_events`, `audit_log`, `import_batches` e `import_issues` conservan hechos, procedencia, actor y ambigüedades.

## Invariantes principales

1. recontratar no crea otra persona;
2. transferir de proyecto no crea otro activo;
3. estado actual nunca borra movimiento anterior;
4. `occurred_at` y `recorded_at` no se confunden;
5. preview de importación no modifica datos;
6. inventario faltante no equivale automáticamente a pérdida;
7. predicción/RUL no retira un activo;
8. evidencia y resolución humana permanecen separadas;
9. cierre de proyecto guarda snapshot y transferencia posterior como evento separado;
10. ubicaciones, tecnologías, perfiles y vocabularios operativos no se hardcodean como universo cerrado.

## Evolución de esquema

Alpha.3 añade tablas sin alterar columnas heredadas, por lo que `create_all()` puede materializar este incremento. En cuanto una release necesite `ALTER`, transformación o eliminación de datos, se debe introducir migración versionada explícita antes de desplegarla.


## Actualización 0.1.0-alpha.4

Se agregaron **6 tablas** y **ninguna tabla existente cambió de forma**:

| Tabla | Para qué |
|---|---|
| `role_areas` | área departamental declarada de un perfil |
| `dashboard_definitions` | vistas resumen (general y por área) |
| `dashboard_widget_placements` | qué widget se muestra, dónde, cómo y para quién |
| `transport_assignments` | unidad ↔ conductor ↔ grupo ↔ radio ↔ teléfono, con periodo |
| `transport_checklists` | checklist de unidad, con `occurred_at` y `recorded_at` |
| `transport_incidents` | incidencias de unidad, con reporte y resolución separados |

### Regla de evolución del esquema

El despliegue usa `Base.metadata.create_all` y **no hay herramienta de
migraciones**. `create_all` crea las tablas que faltan pero **no** altera las
existentes. Por eso:

> Sólo se AGREGAN tablas. No se añaden, renombran ni eliminan columnas de una
> tabla que ya tiene datos en producción.

Las tres salidas legítimas cuando hace falta un dato nuevo sobre una entidad
existente —`metadata_json`, tabla satélite 1:1 y tabla de periodos— están
explicadas en `docs/33_GUIA_DESARROLLO_MULTIDESARROLLADOR.md`.

El significado operativo de cada dominio está en
`docs/28_MODELO_DOMINIO_POR_AREA.md`.
