# 22 · RBAC y perfiles configurables

## Regla

Los **permisos técnicos** sí son parte del código porque representan contratos de seguridad. Los **perfiles de negocio** no están limitados a nombres hardcodeados.

## Perfiles base

Se siembran perfiles protegidos para que el sistema pueda operar desde una instalación nueva:

- ADMIN;
- OFFICE;
- HR;
- HSE;
- SUPERVISOR;
- MATERIAL;
- TALLER.

El bootstrap puede resincronizar estos perfiles base con la versión del producto.

## Perfiles personalizados

Un administrador con `roles.manage` puede crear, por ejemplo:

- `ADMIN_NODOS_B`;
- `RESPONSABLE_RADIOS`;
- `CONSULTA_JEFATURA`;
- cualquier otro perfil futuro.

El perfil selecciona permisos desde la matriz de `permissions` sin modificar Python.

## Protección

- los perfiles base no se editan por el endpoint genérico;
- se pueden crear perfiles derivados/personalizados;
- no se puede retirar `ADMIN` al último administrador activo;
- asignar un rol no crea permisos inexistentes.

## Permisos alpha.3

Además de los heredados de Oficina, se incorporan:

- `roles.manage`;
- `catalogs.manage`;
- `organizations.manage`;
- `locations.manage`;
- `attendance.manage`;
- `assets.view/create/edit/move/bulk`;
- `nodes.view/operate`;
- `maintenance.view/manage`;
- `inventory.manage/closeout`;
- `evidence.view/manage`.

## Motivo

La operación real cambia por proyecto y contratista. Modelar cada combinación como `if role == ...` haría el sistema rígido. La matriz permite adaptar responsabilidades sin convertir permisos en código de negocio.


## Actualización 0.1.0-alpha.4

El catálogo pasó a **37 permisos** y **8 roles semilla**. Los cambios:

| Cambio | Detalle |
|---|---|
| `transport.view` | consultar unidades, conductores y asignaciones |
| `transport.manage` | administrar unidades, checklist e incidencias de transporte |
| `dashboard.configure` | modo DEV: definir qué widgets aparecen en cada vista resumen |
| rol `TRANSPORTE` | nuevo rol semilla del área de Transporte |
| `transport.view` añadido a | `HR`, `SUPERVISOR`, `MATERIAL` y `TALLER`, que necesitan consultar unidades |

### Permisos y autoridad son cosas distintas

El RBAC responde a *qué operación técnica* puede ejecutar un usuario. Quién
**responde** por cada dato —y quién puede proponer frente a quién puede
confirmar— se declara aparte, en la matriz de autoridad por área. Ver
`docs/29_AUTORIDAD_DATO_POR_AREA.md`.

### Área de un perfil

Un perfil puede declarar su área con `PUT /api/roles/{nombre}/area`. Se guarda en
la tabla `role_areas` —no como columna de `roles`, para respetar la regla de
actualización aditiva—.

**El área no autoriza nada.** Agrupa la navegación y decide qué vista resumen
departamental se ofrece primero. Un perfil sin área se considera `GENERAL` y
conserva exactamente los permisos que tenga.
