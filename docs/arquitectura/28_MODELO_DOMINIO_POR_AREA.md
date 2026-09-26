# 28 · Modelo de dominio por área

Complementa `docs/06_MODELO_DATOS.md` (tablas) explicando **qué significa cada
cosa en la operación** y por qué cada área se ve distinta aunque comparta
Tracking Core.

## RRHH · la vida laboral de una persona

```
Person ───┬── EmploymentEngagement ──┬── ContractPeriod
          │   (una por contratación) ├── EmploymentLifecycleEvent
          │                          └── EngagementOrganizationLink ── Organization
          ├── PersonHRProfile   (categoría, licencia, rotación, teléfono)
          ├── PersonAssignment  (proyecto, grupo, ubicación, supervisor, unidad)
          ├── GroupAssignment   (cuadrilla)
          ├── AttendanceRecord
          ├── TrainingRecord ── TrainingCourse
          ├── EppRequest / EppHistory
          └── CaseRecord
```

**`Person` es la identidad; `EmploymentEngagement` es la contratación.** Una
persona puede tener varias contrataciones a lo largo del tiempo, con IDs
laborales distintos, empleadores distintos y huecos entre ellas. El expediente
las muestra todas porque cuelgan del mismo `person_id`.

Una baja cierra la contratación (`end_date`) y, si no queda ninguna vigente,
marca la persona inactiva. **No** borra ni anonimiza nada: su historia sigue
siendo consultable.

`provider` (texto histórico heredado de alpha.2) convive con `Organization`
normalizada. No se borró para no perder lo capturado antes.

## Operación · el ciclo de campo de un nodo

```
Asset (tipo con capacidad node_field)
  ├── NodeOperationItem ── NodeOperation   (lote: TENDIDO, ROTACIÓN, LEVANTADO, RETORNO, INCIDENT)
  ├── AssetMovement                        (traducción del resultado a movimiento)
  ├── AssetCustody
  ├── MaintenanceOrder ── MaintenancePart
  ├── AssetHealthObservation
  └── InventoryCount ── InventorySession
```

Un nodo participa en **operaciones por lote**, con línea y estaca origen/destino,
responsable y participantes. Cada ítem lleva `result_code`, que el catálogo
`NODE_RESULT` traduce a un movimiento y a un estado.

Estados cubiertos: `DEPLOYED` (plantado), `RETURNED`, `DAMAGED`, `BURNED`,
`MISSING`, `LOST`, `STOLEN`, `SEIZED`, `MAINTENANCE`, `HIBERNATED`, `NO_INFO`
(retorno sin información), `RETIRED`.

El sistema responde: **dónde estuvo, qué ocurrió, quién intervino y cuál es su
situación actual** — y muestra de qué movimiento se derivó ese estado.

## Control de Material · custodia e inventario

```
AssetType (capacidades) ── Asset ──┬── AssetIdentifier  (SERIE, IMEI, QR, ECONOMIC_NUMBER, …)
AssetTechnology ───────────────────┤
                                   ├── AssetCustody     (quién lo tiene, con periodo)
                                   ├── AssetMovement    (entregas, devoluciones, transferencias)
                                   ├── InventoryCount
                                   └── EvidenceRecord
Project ── ProjectCloseout   (snapshot inmutable del corte de material)
```

**Activo ≠ proyecto.** Serie, IMEI, QR e identidad sobreviven a las
transferencias. `current_project_id` es dónde está *ahora*, no a quién pertenece.

Un faltante de inventario es una **observación** (`InventoryCount.found = false`),
no una baja. Declarar la pérdida es un movimiento explícito y separado.

## Transporte · unidades y asignaciones

```
Asset (tipo con capacidad transport)
  ├── TransportAssignment  ── Person (conductor), WorkGroup, Project, Location
  │                        └── Asset (radio), Asset (teléfono)
  ├── TransportChecklist
  ├── TransportIncident ── MaintenanceOrder (opcional)
  └── MaintenanceOrder, AssetMovement, EvidenceRecord
```

La unidad **es** un activo del Asset Core; el radio y el teléfono también. No
hay registro paralelo de vehículos ni de radios: `TransportAssignment` sólo
declara la **relación temporal** entre ellos.

Reasignar cierra la asignación anterior con fecha. Quién conducía una unidad el
día de una incidencia sigue siendo consultable después de reasignarla.

`items_json` del checklist guarda las respuestas tal como se capturaron, en vez
de columnas fijas: los puntos de revisión cambian entre proyectos y tipos de
unidad, y congelarlos en el esquema obligaría a migrar la base cada vez.

## Taller / TX · diagnóstico y reparación

```
MaintenanceOrder ──┬── MaintenancePart  (serial retirado / serial instalado)
                   └── Asset
AssetHealthObservation  (SOH, RUL, health score, fuente, confianza)
```

Recepción → diagnóstico → espera de pieza → prueba → reparado / no reparable →
cerrada. Con `downtime_minutes` y piezas con serial retirado e instalado.

**Un evento de taller no es un movimiento de custodia.** Describe la
intervención técnica; se relaciona con el historial del activo pero se registra
aparte, y así se muestra en la ficha.

**Predicción ≠ hecho**: `AssetHealthObservation` nunca cambia el estado factual.

## Evidencias · transversal

```
EvidenceRepository (LOCAL | SMB) ── EvidenceRecord ── (entity_type, entity_id)
```

Los archivos pesados pueden quedarse en el NAS. Server Oficina registra la
relación con la entidad, la ruta relativa, el hash, el tamaño, el MIME, la
procedencia y el usuario. La evidencia es compartida por diseño; el área
competente decide qué significa.

## Tablas incorporadas en esta versión

Todas **nuevas**; ninguna tabla existente cambió de forma (ver doc 33).

| Tabla | Para qué |
|---|---|
| `role_areas` | área departamental de un perfil |
| `dashboard_definitions` | vistas resumen (general y por área) |
| `dashboard_widget_placements` | qué widget se muestra, dónde, cómo y para quién |
| `transport_assignments` | unidad ↔ conductor ↔ grupo ↔ radio ↔ teléfono, con periodo |
| `transport_checklists` | checklist de unidad |
| `transport_incidents` | incidencias de unidad |
