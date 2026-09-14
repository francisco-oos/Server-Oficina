# 20 · Taller, mantenimiento y vida útil

## Separación de conceptos

Server Oficina no representa la vida útil como un único porcentaje mágico. Distingue:

1. **hechos:** edad, horas, ciclos, fallas, piezas, reparaciones, tiempo fuera de servicio;
2. **condición observada:** SOH, health score, métricas de batería/sensores;
3. **diagnóstico:** causa probable/confirmada;
4. **pronóstico:** RUL u otra estimación futura con fuente y confianza;
5. **decisión humana:** reparar, retornar a campo, hibernar, retirar, etc.

## Tablas

- `maintenance_orders`;
- `maintenance_parts`;
- `asset_health_observations`;
- `asset_movements`;
- `operational_events`.

## Orden de mantenimiento

Una orden registra:

- activo;
- prioridad;
- síntoma;
- código de falla;
- diagnóstico;
- acción realizada;
- resultado;
- apertura/cierre;
- downtime;
- usuario que abrió/cerró.

Las piezas pueden conservar serial retirado e instalado. Esto permite saber, por ejemplo, qué batería fue sustituida y en qué reparación.

## Salud/RUL

`asset_health_observations` puede recibir resultados de NodeHealthAnalyzer u otra herramienta futura:

- `soh_percent`;
- `rul_days`;
- `health_score`;
- `confidence`;
- ciclos/horas;
- payload original normalizado.

### Invariante

**Insertar un pronóstico jamás cambia automáticamente `assets.status_code`.**

Una observación puede advertir y alimentar dashboard, pero la transición factual se registra mediante un movimiento autorizado.

## Referencias conceptuales

- ISO 55000: gestión del ciclo de vida y valor del activo;
- ISO 14224: categorías de datos de equipo, falla y mantenimiento;
- ISO 17359 / ISO 13379 / ISO 13381: condición, diagnóstico y pronóstico;
- NodeHealthAnalyzer propio: batería, anomalías, sustitución predictiva y RUL.

Estas referencias guían el modelo; no se copian implementaciones ni se afirma cumplimiento normativo automático.
