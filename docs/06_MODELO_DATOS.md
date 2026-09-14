# 06 · Modelo de datos 0.1

## Identidad y acceso

- `users`
- `roles`
- `permissions`
- `user_roles`
- `role_permissions`
- `session_tokens`

Las sesiones son opacas y revocables; la cookie contiene el token bruto y la BD sólo su SHA-256.

## Organización

- `projects`: contexto operacional;
- `persons`: identidad humana estable;
- `employment_engagements`: alta/recontratación + ID laboral de ese periodo;
- `contract_periods`: renovaciones/periodos, especialmente outsourcing;
- `work_groups`;
- `group_assignments`: pertenencia temporal.

## Oficina

- `attendance_records`;
- `epp_requests`;
- `epp_history`;
- `training_courses`;
- `training_records`;
- `cases`;
- `evidence`.

## Trazabilidad

- `operational_events`: evento transversal con `occurred_at`, `recorded_at`, proyecto, fuente y payload;
- `audit_log`: quién cambió qué entidad y cuándo;
- `import_batches`: archivo original, SHA-256, preview/commit;
- `import_issues`: ambigüedades/conflictos que requieren revisión.

## Invariantes

1. una recontratación crea `employment_engagement`, no otra `person`;
2. un cambio de grupo cierra la asignación anterior y crea otra;
3. una solicitud EPP no actualiza historial oficial hasta validación RRHH;
4. un caso abierto no implica sanción;
5. `occurred_at` y `recorded_at` nunca se confunden;
6. una importación no modifica datos durante PREVIEW;
7. el archivo original se conserva con hash.


## Límites alpha.2

No se agregan tablas paralelas de activos ni otro schema `core`. La fuente funcional sigue siendo el modelo SQLAlchemy existente. Los modelos futuros de Asset Core/roster/vigencia de cursos están documentados, no activos.

Cuando se implemente una evolución de esquema con datos reales, se deberá introducir un mecanismo explícito de migraciones versionadas antes de modificar columnas/tablas existentes; `create_all` sólo cubre bootstrap/adiciones iniciales y no sustituye migraciones de producción.
