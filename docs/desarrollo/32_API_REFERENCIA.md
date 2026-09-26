# 32 · Referencia de API

Todos los endpoints viven bajo `/api`. La autenticación es por cookie de sesión
opaca (`HttpOnly`, `SameSite=Lax`). Cada ruta declara el permiso que exige; el
área **no** autoriza por sí sola.

Errores: `401` sin sesión · `403` sin permiso · `404` no encontrado ·
`409` conflicto de estado · `422` dato inválido. El cuerpo lleva `detail` con un
mensaje en español dirigido al operador.

## Sesión y arranque

| Método | Ruta | Permiso | Notas |
|---|---|---|---|
| `GET` | `/api/health` | público | versión y estado. **Contrato de despliegue: no puede romperse.** |
| `GET` | `/api/setup/status` | público | `needs_setup` |
| `POST` | `/api/setup/first-admin` | público, un solo uso | sólo si no existen usuarios |
| `POST` | `/api/auth/login` | público | crea sesión |
| `POST` | `/api/auth/logout` | sesión | revoca sesión |
| `GET` | `/api/me` | sesión | identidad, roles y permisos |
| `GET` | `/api/me/context` | sesión | identidad + permisos + áreas + dominios |

## Áreas y autoridad del dato

| Método | Ruta | Permiso |
|---|---|---|
| `GET` | `/api/areas` | sesión |
| `GET` | `/api/areas/authority` | sesión |
| `GET` | `/api/roles/{nombre}/area` | sesión |
| `PUT` | `/api/roles/{nombre}/area` | `roles.manage` |

Leer la matriz no revela datos, sólo su gobierno; por eso basta con sesión.

## Vista resumen

| Método | Ruta | Permiso |
|---|---|---|
| `GET` | `/api/dashboards` | `dashboard.view` |
| `GET` | `/api/dashboards/{key}` | `dashboard.view` |
| `GET` | `/api/dev/widgets` | `dashboard.configure` |
| `GET` · `PUT` | `/api/dev/dashboards/{key}` | `dashboard.configure` |
| `POST` | `/api/dev/dashboards` | `dashboard.configure` |
| `PATCH` · `DELETE` | `/api/dev/dashboards/{key}` | `dashboard.configure` |
| `GET` | `/api/dashboard` | `dashboard.view` | **heredado**, forma alpha.2/alpha.3 |

Detalle en `docs/30_DASHBOARD_CONFIGURABLE_Y_WIDGETS.md`.

## Búsqueda transversal y expedientes

| Método | Ruta | Permiso | Devuelve |
|---|---|---|---|
| `GET` | `/api/search?q=` | `dashboard.view` | resultados tipificados con `dossier` y `matched_on` |
| `GET` | `/api/dossier/person/{id}` | `person.view` | expediente integral |
| `GET` | `/api/dossier/person/{id}/summary` | `person.view` | bloque de localización |
| `GET` | `/api/dossier/asset/{id}` | según dominio | ficha de nodo, activo o unidad |
| `GET` | `/api/locate?q=` | `dashboard.view` | **heredado**, localizador alpha.3 |

`/api/dossier/asset/{id}` devuelve `kind` (`node` · `asset` · `transport-unit`) y
exige el permiso del dominio: un nodo requiere `nodes.view`, no sólo
`assets.view`.

`/api/search` omite lo que el usuario no podría abrir e informa cuántas
coincidencias ocultó en `hidden_by_permissions`.

## RRHH

| Método | Ruta | Permiso |
|---|---|---|
| `GET` · `POST` | `/api/persons` | `person.view` · `person.edit` |
| `GET` | `/api/persons/{id}` | `person.view` |
| `POST` | `/api/persons/{id}/rehire` | `person.edit` |
| `GET` · `PUT` | `/api/persons/{id}/hr-profile` | `person.view` · `person.edit` |
| `GET` · `POST` | `/api/persons/{id}/assignments` | `person.view` · `person.edit` |
| `POST` | `/api/engagements/{id}/end` | `person.edit` |
| `POST` | `/api/engagements/{id}/contracts` | `person.edit` |
| `POST` | `/api/engagements/{id}/lifecycle` | `person.edit` |
| `GET` · `POST` | `/api/engagements/{id}/organizations` | `person.view` · `person.edit` |
| `POST` | `/api/attendance` | `attendance.manage` |
| `GET` · `POST` | `/api/epp/requests` | `epp.view` · `epp.request` |
| `POST` | `/api/epp/requests/{id}/review` | `epp.validate_hr` |
| `GET` · `POST` | `/api/organizations` | `person.view` · `organizations.manage` |

Una recontratación conserva `person_id`. Cerrar la última relación laboral marca
la persona inactiva pero **no** borra su identidad.

## Seguridad / HSE

| Método | Ruta | Permiso |
|---|---|---|
| `GET` · `POST` | `/api/training/courses` | `training.view` · `training.schedule_hr` |
| `GET` · `POST` | `/api/training/records` | `training.view` · `training.schedule_hr` |
| `POST` | `/api/training/records/{id}/complete` | `training.confirm_hse` |
| `GET` · `POST` | `/api/cases` | `cases.create` |
| `POST` | `/api/cases/{id}/evidence` | `cases.create` |
| `POST` | `/api/cases/{id}/resolve` | `cases.resolve` |

RRHH programa, HSE acredita. Crear un caso y resolverlo son permisos distintos.

## Transporte

| Método | Ruta | Permiso |
|---|---|---|
| `GET` | `/api/transport/units` | `transport.view` |
| `GET` | `/api/transport/units/{id}` | `transport.view` |
| `POST` | `/api/transport/units/{id}/assignments` | `transport.manage` |
| `POST` | `/api/transport/units/{id}/checklists` | `transport.manage` |
| `GET` | `/api/transport/checklists` | `transport.view` |
| `POST` | `/api/transport/units/{id}/incidents` | `cases.create` |
| `GET` | `/api/transport/incidents` | `transport.view` |
| `POST` | `/api/transport/incidents/{id}/resolve` | `transport.manage` |

Reportar exige `cases.create` (cualquier área que presencie el hecho); resolver
exige `transport.manage` (la autoridad del dominio). Asignar cierra la
asignación anterior con fecha en lugar de sobrescribirla.

## Control de Material y Asset Core

| Método | Ruta | Permiso |
|---|---|---|
| `GET` · `POST` | `/api/assets` | `assets.view` · `assets.create` |
| `GET` | `/api/assets/{id}` | `assets.view` |
| `POST` | `/api/assets/{id}/movements` | `assets.move` |
| `POST` | `/api/assets/bulk/preview` · `/api/assets/bulk/{id}/commit` | `assets.bulk` |
| `GET` · `POST` · `PUT` | `/api/asset-types` | `assets.view` · `catalogs.manage` |
| `GET` · `POST` | `/api/asset-technologies` | `assets.view` · `catalogs.manage` |
| `POST` | `/api/assets/{id}/health` | `maintenance.manage` |
| `GET` · `POST` | `/api/inventory/sessions` | `assets.view` · `inventory.manage` |
| `POST` | `/api/inventory/sessions/{id}/count` | `inventory.manage` |
| `POST` | `/api/inventory/sessions/{id}/close` | `inventory.closeout` |
| `GET` · `POST` | `/api/projects/{id}/material-closeout` | `inventory.closeout` |
| `GET` | `/api/projects/{id}/material-closeouts` | `assets.view` |

Cerrar un inventario no da de baja nada: produce una lista de faltantes
**observados**. El cierre de proyecto guarda un snapshot inmutable.

## Operación · Tracking Nodes

| Método | Ruta | Permiso |
|---|---|---|
| `GET` | `/api/node-operations` | `nodes.view` |
| `POST` | `/api/node-operations` | `nodes.operate` |

Una operación por lote afecta a varios nodos. `result_code` se traduce a
movimiento y estado mediante metadatos del catálogo `NODE_RESULT`, nunca por
condicionales sobre cadenas.

## Taller / TX

| Método | Ruta | Permiso |
|---|---|---|
| `GET` · `POST` | `/api/maintenance` | `maintenance.view` · `maintenance.manage` |
| `PUT` | `/api/maintenance/{id}` | `maintenance.manage` |
| `POST` | `/api/maintenance/{id}/parts` | `maintenance.manage` |

## Evidencias

| Método | Ruta | Permiso |
|---|---|---|
| `GET` · `POST` | `/api/evidence/repositories` | `evidence.view` · `evidence.manage` |
| `POST` | `/api/evidence/upload` | `evidence.manage` |
| `POST` | `/api/evidence/register-existing` | `evidence.manage` |
| `GET` | `/api/evidence/records` | `evidence.view` |

Subida en streaming con SHA-256, archivo temporal y promoción atómica.
Fail-closed si el repositorio SMB deja de estar montado. La indexación de un
archivo existente valida que la ruta resuelta no escape del repositorio.

## Importaciones

| Método | Ruta | Permiso |
|---|---|---|
| `POST` | `/api/imports/{kind}/preview` | `attendance.import` |
| `POST` | `/api/imports/{id}/commit` | `imports.commit` |
| `GET` | `/api/imports/{id}/issues` | `attendance.import` |

Nada se escribe hasta el commit. Ver `docs/34_CONTRATO_INGESTA_DOCUMENTAL.md`.

## Administración

| Método | Ruta | Permiso |
|---|---|---|
| `GET` · `POST` | `/api/users` | `users.manage` |
| `PUT` | `/api/users/{id}/roles` | `users.manage` |
| `GET` | `/api/roles` | sesión |
| `POST` · `PUT` | `/api/roles` · `/api/roles/{nombre}` | `roles.manage` |
| `GET` | `/api/permissions` | `roles.manage` |
| `GET` · `POST` · `PUT` | `/api/catalogs/...` | sesión · `catalogs.manage` |
| `GET` · `POST` | `/api/projects` · `/api/groups` | sesión · `projects.manage` |
| `GET` · `POST` | `/api/locations` | sesión · `locations.manage` |
| `GET` | `/api/audit` | `audit.view` |

Los perfiles base están protegidos y no puede quedarse el sistema sin
administrador.
