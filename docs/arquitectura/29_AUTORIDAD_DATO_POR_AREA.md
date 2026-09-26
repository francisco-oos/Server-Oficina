# 29 · Autoridad sobre el dato por área

## Por qué existe esta matriz

Server Oficina es un servidor **compartido**. Que RRHH, HSE, Transporte,
Material, Operación y Taller trabajen sobre el mismo Tracking Core no significa
que cualquiera pueda modificar cualquier dato.

El RBAC (`app/core/rbac.py`) responde a *qué operación técnica* puede ejecutar un
usuario. Esta matriz responde a algo distinto y complementario:

```
QUIÉN ES AUTORIDAD SOBRE EL DATO     el área que responde por su veracidad
QUIÉN LO PUEDE CONSULTAR             áreas que lo leen para trabajar
QUIÉN PUEDE PROPONER UN CAMBIO       áreas que pueden reportar un hecho
QUIÉN PUEDE CONFIRMARLO              áreas que lo vuelven oficial
```

La distinción **proponer ≠ confirmar** es la clave. Operación puede reportar que
un nodo apareció dañado (un hecho observado). La baja definitiva del activo la
confirma Control de Material. Es la misma lógica que `evidencia ≠ sanción`.

## Dónde vive

`app/core/areas.py`, como datos declarativos. La API la publica en
`GET /api/areas/authority` y la interfaz la muestra en **Administración ›
Autoridad del dato**. Documentación, API y pantalla leen de la misma fuente,
así que no pueden divergir.

## Áreas

| Código | Área | Responsabilidad |
|---|---|---|
| `RRHH` | Recursos Humanos | identidad laboral, contrataciones, asignaciones, asistencia, EPP |
| `HSE` | Seguridad / HSE | cursos de seguridad, cumplimiento, incidencias HSE |
| `TRANSPORTE` | Transporte | unidades, conductores, asignaciones, checklist |
| `MATERIAL` | Control de Material | inventario, custodia, entregas, existencia física |
| `OPERACION` | Operación / Tracking Nodes | historia operacional de nodos |
| `TALLER` | Taller / TX | diagnóstico, pruebas, reparación, resultado técnico |
| `GENERAL` | Transversal | consulta transversal y administración |

## Matriz de gobierno

| Dominio | Autoridad | Consulta | Propone | Confirma |
|---|---|---|---|---|
| Identidad laboral | RRHH | HSE, TRANSPORTE, MATERIAL, OPERACION, TALLER | HSE, TRANSPORTE, OPERACION | RRHH |
| Contrataciones / altas / bajas | RRHH | todas | — | RRHH |
| Grupos, supervisor, ubicación | RRHH | todas | TRANSPORTE, OPERACION | RRHH |
| Asistencia y rotación | RRHH | HSE, TRANSPORTE, OPERACION | OPERACION | RRHH |
| Solicitudes y entregas de EPP | RRHH | HSE, MATERIAL, OPERACION | HSE, OPERACION, MATERIAL | RRHH |
| Cursos de seguridad | **HSE** | RRHH, TRANSPORTE, OPERACION | RRHH | HSE |
| Incidencias HSE y casos | **HSE** | RRHH, TRANSPORTE, MATERIAL, OPERACION | todas | HSE, RRHH |
| Unidades y conductores | **TRANSPORTE** | RRHH, HSE, MATERIAL, OPERACION | RRHH, OPERACION | TRANSPORTE |
| Checklist e incidencias de unidad | **TRANSPORTE** | HSE, MATERIAL, TALLER | OPERACION, HSE | TRANSPORTE |
| Existencia física y custodia | **MATERIAL** | todas | OPERACION, TALLER, TRANSPORTE | MATERIAL |
| Identidad del activo | **MATERIAL** | RRHH, TRANSPORTE, OPERACION, TALLER | TALLER, OPERACION | MATERIAL |
| Historia operacional de nodos | **OPERACION** | MATERIAL, TALLER, HSE | MATERIAL, TALLER | OPERACION |
| Diagnóstico y reparación | **TALLER** | MATERIAL, OPERACION, TRANSPORTE | MATERIAL, OPERACION, TRANSPORTE | TALLER |
| Observaciones SOH / RUL | **TALLER** | MATERIAL, OPERACION | MATERIAL, OPERACION | TALLER |
| Repositorios y evidencias | GENERAL | todas | todas | GENERAL |

## Cómo se materializa en código

La autoridad se ejerce mediante permisos. Ejemplo verificado por
`test_incident_reported_by_any_area_resolved_by_transport`:

| Acto | Permiso | Quién lo tiene |
|---|---|---|
| Reportar una incidencia de unidad | `cases.create` | casi todas las áreas |
| Resolverla | `transport.manage` | sólo Transporte y ADMIN |

Lo mismo en EPP (`epp.request` vs `epp.validate_hr`) y en capacitación
(`training.schedule_hr` vs `training.confirm_hse`).

## Área de un perfil

Un perfil declara su área en la tabla `role_areas`
(`PUT /api/roles/{nombre}/area`). Se modela como tabla aparte, y no como columna
de `roles`, para respetar la regla de actualización aditiva.

**El área nunca autoriza.** Un perfil sin área declarada se considera `GENERAL`
y conserva exactamente los permisos que tenga. El área sólo agrupa la
navegación y decide qué vista resumen departamental se le ofrece primero.
