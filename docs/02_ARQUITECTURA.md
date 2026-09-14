# 02 · Arquitectura

## Decisión principal

**Monolito modular** sobre una fuente de verdad PostgreSQL.

Se evita comenzar con microservicios en una Latitude 7220 i3/8 GB. El aislamiento se logra por contratos, módulos, permisos y fronteras de datos; un módulo pesado podrá extraerse a un servicio independiente cuando exista una necesidad demostrada.

## Capas

```text
Navegador LAN
   │
   ▼
FastAPI + UI web estática
   │
   ├── Auth / RBAC
   ├── Oficina / Personal (entrega actual)
   ├── Importaciones
   ├── EPP
   ├── Capacitación
   ├── Casos / Evidencias
   └── Tracking Core
          ├── identidad permanente
          ├── relaciones temporales
          ├── proyectos
          ├── eventos
          ├── procedencia
          ├── auditoría
          └── evidencias
   │
   ▼
PostgreSQL 18.6 (Docker) + /srv/server-oficina
```

## Tracking Core

No se modela todo como una tabla genérica. Se usa un **modelo híbrido**:

- tablas de dominio con datos especializados;
- `operational_events` como historia transversal;
- relaciones temporales explícitas;
- evidencia y procedencia preservadas;
- un "estado actual" puede derivarse/optimizarse sin borrar historia.

## Temporalidad

Un evento separa:

- `occurred_at`: cuándo ocurrió realmente;
- `recorded_at`: cuándo llegó al servidor.

Esto permite cargar información atrasada sin falsificar la cronología de la operación.

## Persona ≠ relación laboral

`persons.id` es estable. `employment_engagements.employment_id` puede cambiar por baja/recontratación. Renovaciones/periodos de outsourcing tienen entidad propia (`contract_periods`).

## Proyectos

El proyecto es contexto, no identidad. Personas y activos sobreviven al proyecto; se vinculan temporalmente a él. El futuro cierre de proyecto será una conciliación auditable, no un reinicio de números de serie.

## Gobierno

El Core separa:

1. **hecho/evento**;
2. **evidencia/fuente**;
3. **caso**;
4. **resolución humana**.

No existe un algoritmo de sanción o etiqueta "buen/mal empleado" en esta versión.


## Despliegue físico alpha.2

La app sigue como proceso `systemd` del host para que UFW controle 8080 con claridad. PostgreSQL se mantiene en Docker y se publica sólo en loopback (`127.0.0.1:5432`). Esta separación evita exponer la base a la LAN y evita consumir el pequeño `/var`.

Código versionado: `/opt/server-oficina/releases/<VERSION>`; activo: `/opt/server-oficina/current`; datos persistentes: `/srv/server-oficina`.
