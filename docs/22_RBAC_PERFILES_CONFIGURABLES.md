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
