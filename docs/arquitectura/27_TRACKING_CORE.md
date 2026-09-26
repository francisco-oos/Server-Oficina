# 27 · Tracking Core

## Qué es

Tracking Core es el conjunto de conceptos que **todas** las áreas comparten por
debajo. No es un módulo ni una tabla: es el acuerdo sobre cómo se representa la
trazabilidad en todo el sistema.

| Concepto | Dónde vive | Invariante que impone |
|---|---|---|
| identidad estable | `persons.id`, `assets.id` | sobrevive a bajas, recontrataciones y transferencias |
| proyecto | `projects` | un activo o una persona pasan por proyectos; no *pertenecen* a uno |
| ubicación | `locations` | configurable en BD; ningún campamento está en el código |
| relación temporal | `*_assignments`, `asset_custody` | periodos con `start`/`end`, nunca un campo «actual» que se sobrescriba |
| responsable | `responsible_person_id` | quién intervino en el hecho, no quién es culpable |
| custodia | `asset_custody` | quién tiene físicamente el activo, con historia |
| evento | `operational_events` | hecho registrado, inmutable |
| estado actual | `assets.status_code` | **derivado** del historial, no fuente de verdad |
| evidencia | `evidence_records` | archivo relacionado, con hash y procedencia |
| procedencia | `source_type` / `source_id` | de dónde salió el dato |
| auditoría | `audit_log` | quién cambió qué, cuándo y desde dónde |
| fecha de ocurrencia vs registro | `occurred_at` / `recorded_at` | dos hechos distintos, ambos se conservan |
| autoridad por área | `app/core/areas.py` | quién responde por cada dato |

## La regla que más se malinterpreta

> **Tracking Core común NO significa interfaz común.**

Que una persona, un nodo, un radio y una camioneta compartan identidad,
historial y evidencias no implica que se administren igual. Cada dominio tiene
su ciclo de vida:

```
RRHH        sigue la vida laboral de una persona
Operación   sigue el ciclo de campo de un nodo
Material    sigue custodia e inventario de un activo
Transporte  sigue unidades, conductores y asignaciones
Taller      sigue diagnóstico, reparación y resultado
```

Por eso existen cuatro constructores de expediente distintos en
`app/services/lookup.py` (`person_dossier`, `node_dossier`, `asset_dossier`,
`transport_dossier`) y cuatro renderizadores distintos en `app/static/app.js`.
La prueba `test_dossier_structures_differ_per_domain` impide que vuelvan a
fundirse en una ficha universal.

## Estado actual ≠ historial

`assets.status_code` es un *caché de consulta*. La verdad está en
`asset_movements` y `node_operation_items`. Por eso la ficha de nodo muestra el
estado **junto a su derivación**:

```json
"current_state": {
  "status_code": "DAMAGED",
  "derived_from": {
    "movement_type": "DAMAGE",
    "occurred_at": "2026-09-14T15:02:00Z",
    "line_code": "L-1200",
    "stake_code": "1010",
    "responsible": "Operador Nodo Díaz"
  }
}
```

Nunca se corrige el pasado: una corrección es un evento nuevo.

## Ocurrió ≠ se registró

`occurred_at` es cuándo pasó en campo. `recorded_at` es cuándo se capturó. El
desfase es información operativa real —una cuadrilla sin cobertura registra al
volver— y se muestra en la interfaz por separado, nunca colapsado.

## Predicción ≠ hecho

`asset_health_observations` guarda SOH, RUL y health score con su fuente y su
confianza. **Ninguna** observación cambia `status_code` ni da de baja un activo.
La decisión es humana y queda como movimiento explícito con su propio actor.

## Cómo se extiende sin romperlo

- **Estado nuevo** → fila en el catálogo `ASSET_STATUS`. Marcar `{"critical": true}`
  lo incorpora automáticamente a los widgets de excepciones.
- **Movimiento nuevo** → fila en `ASSET_MOVEMENT` con `status_after` en metadatos.
- **Resultado de campo nuevo** → fila en `NODE_RESULT` con `movement_type`.
- **Tipo de activo nuevo** → fila en `asset_types` con sus **capacidades**.
  Las capacidades deciden el comportamiento; el nombre del tipo nunca.

Ver `docs/33_GUIA_DESARROLLO_MULTIDESARROLLADOR.md`.
