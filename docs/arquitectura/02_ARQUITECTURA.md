# 02 · Arquitectura vigente — alpha.3

## Decisión principal

**Monorepo + monolito modular** sobre PostgreSQL. La Latitude 7220 no necesita microservicios para resolver este dominio; las fronteras se mantienen mediante módulos, permisos, contratos de datos y pruebas.

```text
Navegador LAN
   │
   ▼
FastAPI + UI web estática
   │
   ├── Auth / RBAC dinámico
   ├── RRHH / Oficina
   ├── Asset Core / inventario
   ├── Tracking Nodes por lote
   ├── Taller / mantenimiento / salud
   ├── Evidencias / NAS
   ├── Importaciones
   └── Tracking Core / auditoría
   │
   ▼
PostgreSQL 18.6 (Docker)
   │
   └── datos persistentes en /srv/server-oficina
```

## Tracking Core

El modelo es híbrido: tablas de dominio especializadas + eventos/movimientos temporales. `assets` y relaciones de personal conservan snapshots actuales para búsqueda rápida, pero la historia autoritativa vive en movimientos, custodias, asignaciones, operaciones y auditoría.

`occurred_at` representa cuándo ocurrió el hecho; `recorded_at`, cuándo llegó al servidor. Esta separación permite reportes atrasados sin falsificar cronología.

## Identidad

- `persons.id` es estable entre baja/recontratación; el ID laboral pertenece a `employment_engagements`.
- `assets.id` es estable entre custodios, ubicaciones y proyectos; serie/IMEI/QR/económico son identificadores asociados.
- proyecto, grupo, ubicación, custodio y estado son contexto temporal, no identidad.

## Configuración, no hardcode

Son configurables en BD: catálogos de estado/movimiento/resultado, ubicaciones, tipos de activo, capacidades, tecnologías, organizaciones, perfiles y permisos de negocio, y repositorios de evidencia. Las semillas permiten arrancar, pero no definen un universo cerrado.

El motor usa **capacidades** (`node_field`, `custody`, `maintenance`, `health`, etc.) en vez de condicionar reglas al nombre de un tipo específico.

## Asset Core y nodos

Un activo mantiene snapshot actual y `asset_movements` preserva cada transición. `node_operations` agrupa operaciones de campo y `node_operation_items` conserva línea/estaca, responsable, participantes, resultado y estado anterior/posterior por equipo. Tendido/rotación/levantado/retorno y excepciones no borran la historia previa.

## Mantenimiento y vida útil

`maintenance_orders`, `maintenance_parts` y `asset_health_observations` separan hechos de mantenimiento, condición y pronóstico. SOH/RUL nunca cambia automáticamente el estado factual del activo.

## Cierre de proyecto

`project_closeouts` guarda un **snapshot auditable** del material del proyecto al momento del cierre: estados, excepciones críticas, material transferible y detalle por activo. Una transferencia posterior a otro proyecto no reescribe ese corte histórico.

## Evidencias y NAS

Server Oficina puede almacenar una carga o **indexar un archivo ya existente** en un repositorio. Repositorios SMB son configurables y operan fail-closed: si el montaje desaparece, no se escribe en una carpeta local sustituta. Las credenciales SMB permanecen fuera de PostgreSQL.

## Despliegue

- código: `/opt/server-oficina/releases/<VERSION>`;
- release activa: `/opt/server-oficina/current`;
- app FastAPI: servicio `systemd` sin privilegios;
- PostgreSQL 18.6: Docker, `127.0.0.1:5432`;
- datos negocio: `/srv/server-oficina`;
- Docker/containerd: `/srv/docker`.

El instalador alpha.3 hace gate de paquete y backup pre-upgrade antes de promover `current`, y revierte el symlink si el health-check de la nueva app falla.
