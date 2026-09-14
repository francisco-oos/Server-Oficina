# 12 · Investigación: ciclo de vida, condición y vida útil de equipos

## Objetivo

Preparar `Asset Core`, nodos, TX y Taller sin convertir Server Oficina en un CMMS genérico ni copiar Snipe-IT/Ralph/GLPI. La operación sí necesita responder **qué equipo es, dónde está, quién lo tiene, qué le ocurrió, qué mantenimiento recibió, qué condición tiene y por qué terminó/reutilizó su vida en un proyecto**.

## Fuentes estudiadas

- ISO 55000:2024 — gestión de activos durante su ciclo de vida y alineación con valor/objetivos organizacionales: https://www.iso.org/standard/83053.html
- ISO 14224:2016 — categorías de datos de equipo, fallas y mantenimiento, incluyendo consecuencias y downtime: https://www.iso.org/standard/64076.html
- ISO 17359:2018 — guía general para estructurar un programa de monitoreo de condición aplicable a máquinas: https://www.iso.org/standard/71194.html
- ISO 13379-1:2025 — conceptos y criterios generales para interpretación de datos y diagnóstico de condición: https://www.iso.org/standard/88027.html
- ISO 13381-1:2025 — guía/requisitos para procesos de pronóstico; refuerza que una estimación de vida restante necesita datos, características, proceso y comportamiento definidos: https://www.iso.org/standard/88029.html
- GS1 EPCIS 2.0 — trazabilidad basada en eventos: qué, cuándo, dónde y contexto/por qué; útil como referencia conceptual, no como obligación de implementar EPCIS: https://www.gs1.org/standards/epcis
- Snipe-IT — patrones de custodia/check-out; estudio solamente por AGPL-3.0.
- Ralph — ciclo de vida flexible/CMDB; estudio solamente, Apache-2.0.
- GLPI — activos, ubicación, incidentes/intervenciones; estudio solamente, GPL-3.0.
- proyecto propio `NodeHealthAnalyzer` — observaciones de salud de batería, anomalías y estimación de vida restante; debe integrarse como fuente, no duplicarse.
- proyecto propio `Tendido-Diario-revision` — reconciliación entre SERCEL/INOVA/comentarios e histórico diario.

## Consecuencia de la investigación de condición y pronóstico

Las referencias ISO 17359/13379/13381 refuerzan una separación que Server Oficina debe conservar:

```text
medición/observación → interpretación/diagnóstico → pronóstico → recomendación → decisión humana
```

No se debe guardar un `remaining_life` como verdad huérfana. Cada pronóstico futuro deberá conservar como mínimo: activo/componente, instante o ventana de datos, variables utilizadas, unidad, método/modelo, versión, horizonte, valor estimado, incertidumbre/confianza cuando exista, archivo/fuente y fecha de cálculo. Una nueva estimación **no borra** la anterior; ambas forman una serie histórica auditable.

Para clases sin telemetría suficiente, el sistema se queda en mantenimiento por calendario/uso/inspección y no inventa RUL. Para nodos, `NodeHealthAnalyzer` continúa siendo el productor especializado de observaciones/estimaciones hasta que exista una razón técnica documentada para mover ese cálculo al servidor.

## Hallazgo principal: “vida útil” no debe ser un único número

Server Oficina debe distinguir al menos:

1. **edad cronológica**: adquisición/alta/puesta en servicio;
2. **uso acumulado**: horas, ciclos, días en campo, rotaciones u otra métrica según tipo;
3. **condición observada**: batería, diagnóstico, hermeticidad, pruebas, anomalías;
4. **historial de fallas**: modo/causa/consecuencia cuando pueda conocerse;
5. **mantenimiento**: preventivo/correctivo, acciones, piezas, resultado, downtime;
6. **vida esperada**: dato técnico/configurable, no sentencia automática;
7. **vida restante estimada**: cálculo/versionado con fuente/modelo y confianza;
8. **decisión humana de retiro/reparación/transferencia**.

No se debe retirar automáticamente un equipo sólo porque un modelo de salud baje de un umbral. El sistema registra observación, recomendación y resolución.


## Evidencia operacional propia recuperada

Además de estándares/repositorios, se contrastó el diseño con evidencia real ya generada en la operación del usuario. **No se copian aquí listados de series, nombres ni datos personales**; sólo se conservan las conclusiones de diseño y la referencia documental.

### Baja administrativa de 45 celulares · 13/08/2026

La nota técnica de baja no decide por antigüedad aislada: combina pérdida de capacidad de batería, fallas de pantalla/táctil, desgaste acumulado, obsolescencia tecnológica, persistencia de fallas, reemplazos previos e incompatibilidad/no reconocimiento de componentes. Esto confirma que `Asset Core` necesita **observaciones + intervenciones + condición + resolución humana** y que `retired` debe guardar motivo, dictamen/evidencia y autoridad que aprueba.

### Auditoría Node Health Analyzer · 16/07/2026

La auditoría interna distingue tres preguntas que Server Oficina debe mantener separadas:

- autonomía operativa hasta warning/critical;
- estado de salud (SOH) de batería;
- riesgo de falla/reemplazo o pronóstico.

También concluye que la extrapolación lineal de voltaje disponible en ese prototipo es **experimental** y no equivale a vida útil validada; los datos faltantes no deben convertirse en falla, y cualquier aprendizaje necesita verdad de campo, versión de reglas/modelo, decisión experta y resultado posterior. Estas conclusiones pasan a ser restricciones explícitas del futuro adaptador `NodeHealthAnalyzer → Server Oficina`.

### Procedimiento de control de inventario de equipo sísmico

El material de capacitación operativa confirma patrones que el futuro módulo de activos debe representar sin cambiar el proceso real: entrega por responsables definidos, conteo al recibir, conciliación de material que salió contra sobrante/retornado, registro de serie/tipo plantado o levantado, estados excepcionales como incautado/no encontrado/siniestrado, anomalía reportada por campo y confirmación mediante bitácora de entrega/recepción.

**Consecuencia:** la custodia no será un campo `responsable_actual` sobrescribible. Será una secuencia de entregas/recepciones/conciliaciones firmadas o validadas, de la cual se deriva el responsable actual.

## Modelo futuro recomendado (NO activo en alpha.2)

```text
assets
asset_identifiers        serie / IMEI / QR / económico / fabricante
asset_project_periods    participación temporal en proyecto
asset_custody_periods    persona/grupo/área responsable
asset_location_periods   almacén/campamento/campo/taller
asset_status_periods     disponible/asignado/mantenimiento/dañado/etc.
asset_meter_readings     horas/ciclos/km/rotaciones según clase
asset_health_observations fuente, métrica, valor, unidad, confianza
maintenance_work_orders  apertura/cierre/prioridad/tipo
maintenance_actions      acción, resultado, recursos, downtime
component_replacements   componente retirado/instalado
asset_events             historia transversal compatible con Tracking Core
project_asset_closure    conciliación al cierre del proyecto
```

Cada tabla especializada conserva semántica de dominio; `operational_events` sigue siendo la historia transversal. No se reemplaza todo por JSON genérico.

## Evento de activo: contrato conceptual

Todo evento importante debe poder responder:

- **qué** activo/objeto estuvo involucrado;
- **cuándo ocurrió** (`occurred_at`) y cuándo se registró (`recorded_at`);
- **dónde** ocurrió o desde qué ubicación se reportó;
- **por qué/contexto**: tipo de operación, proyecto, causa/referencia;
- **quién/fuente** lo reportó;
- **evidencia** asociada;
- **estado anterior/posterior**, cuando aplique.

Este patrón está alineado conceptualmente con EPCIS, pero Server Oficina conserva su vocabulario operacional propio.

## Nodos sísmicos

Los nodos serán una especialización de `asset`, no una identidad paralela. Se prevén eventos/observaciones como:

```text
RECEIVED → DIAGNOSED → REPAIRING → TESTED → HIBERNATED/READY
→ ISSUED_FIELD → PLANTED → ROTATED → LIFTED → RETURNED
→ DAMAGED / LOST / STOLEN / SEIZED / NOT_FOUND / RETIRED
```

El flujo real no será una máquina de estados rígida universal: habrá transiciones excepcionales justificadas y auditadas.

`NodeHealthAnalyzer` deberá aportar observaciones como batería/descarga/anomalía/RUL con: fecha del dato, algoritmo/modelo, versión, valor, confianza y archivo fuente. Server Oficina no recalculará de forma oculta ni sobrescribirá la observación original.

## Cierre de proyecto

El cierre debe reconstruir:

```text
stock inicial
+ altas/compras/transferencias entrantes
- bajas definitivas/transferencias salientes
± movimientos y conciliaciones
= material sobreviviente físicamente verificado
```

Los activos sobrevivientes conservan `asset_id` y toda su historia; sólo se cierra su periodo del proyecto anterior y se abre el del siguiente.

## Métricas que podrán derivarse cuando exista dato suficiente

- disponibilidad;
- downtime acumulado;
- número de fallas/reparaciones;
- tiempo medio entre fallas y tiempo medio de reparación, sólo con eventos consistentes;
- horas/ciclos/kilómetros/rotaciones;
- condición/health trend;
- porcentaje de vida técnica esperada consumida;
- vida restante estimada con procedencia explícita.

**Descartado:** usar depreciación contable como sustituto de vida técnica. Podrá existir en otro módulo si negocio la necesita, pero no gobierna condición mecánica/electrónica.
