# Reporte de seguridad · 0.1.0-alpha.4

Revisión de seguridad de los cambios de esta evolución, sobre la línea base de
`SECURITY.md`.

## Superficie añadida

| Área | Endpoints nuevos | Permiso exigido |
|---|---:|---|
| Áreas y autoridad del dato | 5 | sesión / `roles.manage` |
| Vista resumen y modo DEV | 7 | `dashboard.view` / `dashboard.configure` |
| Búsqueda y expedientes | 4 | según dominio |
| Transporte | 8 | `transport.view` / `transport.manage` / `cases.create` |

**Ningún endpoint nuevo es anónimo.** Los únicos públicos siguen siendo
`/api/health`, `/api/setup/status` y `/api/setup/first-admin` (de un solo uso).

## Control de acceso

### La configuración del dashboard no puede escalar privilegios

Riesgo evaluado: un administrador coloca en el dashboard de alguien un widget
que expone datos de un área a la que ese usuario no tiene acceso.

**Mitigación**: cada widget declara su permiso y el renderizado lo verifica
**siempre**, con independencia de la configuración. La restricción por perfil
(`role_names`) sólo puede **acotar** por encima del permiso, nunca ampliarlo.

Probado por `test_dashboard_render_filters_widgets_by_permission` y
`test_placement_role_restriction_narrows_only`.

### Las fichas exigen el permiso de su dominio

Abrir la ficha de un nodo exige `nodes.view`, no basta `assets.view`. La ficha
de una unidad exige `transport.view`. Probado por
`test_asset_dossier_requires_the_permission_of_its_domain`.

### La búsqueda transversal no filtra sólo en la interfaz

`/api/search` descarta en el **servidor** los resultados cuya ficha el usuario no
podría abrir, y devuelve `hidden_by_permissions` con el número omitido.

Decisión consciente: revelar el **número** de coincidencias ocultas es una fuga
mínima y deliberada. La alternativa —fingir que no existen— lleva al operador a
concluir que un equipo no está registrado y a darlo de alta por duplicado. Se
revela un conteo, nunca una etiqueta, un identificador ni un estado.

### Proponer no es confirmar

Reportar una incidencia de unidad exige `cases.create`; resolverla exige
`transport.manage`. Probado por
`test_incident_reported_by_any_area_resolved_by_transport`, que verifica el 403.

### El área no autoriza

`role_areas` agrupa la navegación y decide qué vista resumen se ofrece primero.
No concede ni retira ningún permiso. Un perfil sin área declarada conserva
exactamente los suyos.

## Validación de entrada

| Entrada | Control |
|---|---|
| Composición de dashboard | widget debe existir en el registro; sin repetidos; tamaño de la lista cerrada; perfil debe existir. Fallo → 422 y **no se escribe nada** |
| Asignación de transporte | disponibilidad de lista cerrada; conductor, radio, teléfono, proyecto, grupo y ubicación verificados contra la base |
| Checklist | resultado de lista cerrada; odómetro `ge=0` |
| Incidencia | tipo y resumen con longitud mínima; la orden de taller debe pertenecer **al mismo activo** |
| Búsqueda | mínimo 2 caracteres; con uno solo devolvería casi el padrón completo, además de ser costoso |
| Área de perfil | debe existir en `AREAS` |

## Inyección

- **SQL**: todas las consultas nuevas usan SQLAlchemy con parámetros ligados.
  Los términos de búsqueda entran en `ilike()` como parámetro, nunca concatenados.
- **XSS**: toda interpolación que llega al DOM pasa por `esc()`. Se revisaron una
  a una las 40 interpolaciones que el escaneo marcó como excepción: todas son
  números calculados o texto que se escapa aguas abajo.
- **Rutas**: 13 construcciones de URL se endurecieron con `encodeURIComponent`.
  No había vector real —los identificadores vienen de la propia API— pero el
  coste de la defensa es nulo.
- **Traversal de evidencias**: sin cambios respecto a alpha.3; la indexación de
  archivos existentes sigue resolviendo la ruta y rechazando lo que escape del
  repositorio.

## Auditoría

Las operaciones nuevas que cambian configuración o estado autorizado quedan en
`audit_log` con actor, antes y después:

```
ROLE_AREA_SET · DASHBOARD_LAYOUT_SET · DASHBOARD_CREATE · DASHBOARD_UPDATE ·
DASHBOARD_DELETE · TRANSPORT_ASSIGN · TRANSPORT_INCIDENT_REPORT ·
TRANSPORT_INCIDENT_RESOLVE
```

Los hechos operativos (checklist, asignación, incidencia) generan además
`OperationalEvent` con `occurred_at`, `recorded_at`, procedencia y actor.

## Aislamiento de fallos

Un widget que lance una excepción devuelve un error genérico en su tarjeta; el
detalle técnico va al log del servicio. **No se filtran trazas ni mensajes de
base de datos a la interfaz.** El resto de la vista resumen se dibuja con
normalidad, de modo que un fallo aislado no deja a un operador sin su pantalla.

## Corrección de permisos de sistema de archivos

El `PermissionError` de la validación manual se corrigió **sin debilitar
permisos**:

- ❌ no se usó `chmod -R 777`;
- ❌ no se hizo escribible `/opt`;
- ❌ no se recomienda ejecutar la validación como root;
- ✅ las pruebas escriben en un directorio temporal privado del sistema, que se
  borra al terminar.

El endurecimiento del servicio systemd (`NoNewPrivileges`, `ProtectSystem`,
`ProtectHome`, usuario sin privilegios) queda intacto, y el árbol desplegado en
`/opt/server-oficina/current` sigue siendo de sólo lectura para el servicio.

## Sin cambios respecto a alpha.3

Contraseñas con `scrypt` y salt · sesión opaca con sólo el SHA-256 en base ·
cookie `HttpOnly` + `SameSite=Lax` · bootstrap de administrador de un solo uso ·
PostgreSQL ligado a `127.0.0.1` · credenciales SMB root-only fuera de la base ·
NAS fail-closed · subidas en streaming con SHA-256 y promoción atómica.

## Límites que siguen vigentes

- HTTP en LAN sin TLS; fuera de la LAN, VPN/HTTPS y cookie `secure`.
- Sin MFA ni SSO.
- Sin límite de intentos de inicio de sesión persistente.
- Sin análisis antivirus de los archivos cargados.
- No abrir 5432 a la LAN ni 8080 a Internet.

## Datos humanos

La plataforma registra hechos y evidencia. **No genera sanciones automáticas ni
puntuación laboral opaca.** Las excepciones de nodos asociadas a una persona se
presentan explícitamente como trazabilidad y no como imputación; la resolución
la firma el área con autoridad y queda auditada.
