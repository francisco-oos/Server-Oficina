# 19 · Asset Core y Tracking Nodes

## Finalidad

Esta capa existe para responder no sólo **qué estado tiene un equipo**, sino **qué le pasó, cuándo, dónde, quién intervino y bajo qué proyecto/grupo**.

## Identidad permanente del activo

`assets.id` es la identidad técnica estable. Un activo no se recrea al cambiar de custodio, grupo o proyecto.

Identificadores externos viven en `asset_identifiers` y admiten, entre otros:

- serie;
- IMEI;
- QR;
- número económico;
- identificadores futuros creados por la operación.

La combinación `kind + value` es única para evitar que un mismo IMEI/QR termine asociado a dos activos.

## Tipos y tecnologías configurables

`asset_types` define nombre y **capacidades**. Ejemplos de capacidades:

- `node_field`;
- `custody`;
- `maintenance`;
- `transport`;
- `health`;
- `imei`.

No se pregunta en código si un tipo se llama exactamente `NODE`; se consulta si declara la capacidad necesaria. Esto permite añadir sensores futuros sin modificar la lógica de Tracking Nodes.

`asset_technologies` separa tecnología/fabricante del tipo de activo. Las semillas SERCEL, INOVA, DJI y GENERIC son editables y no limitan el sistema.

## Estado actual y trazabilidad

`assets` conserva un snapshot actual para consultas rápidas:

- estado;
- proyecto;
- grupo;
- ubicación;
- custodio.

La historia autoritativa se conserva en:

- `asset_movements`;
- `asset_custody`;
- `operational_events`.

Por tanto, actualizar el snapshot no elimina la transición anterior.

## Operaciones de nodos

Una `node_operation` representa una operación/lote de campo y `node_operation_items` registra cada activo involucrado.

Tipos iniciales:

- TENDIDO;
- ROTACION;
- LEVANTADO;
- RETORNO;
- INCIDENT.

Cada item puede conservar:

- estaca origen;
- estaca destino;
- resultado;
- estado anterior;
- estado posterior;
- responsable;
- participantes;
- línea;
- proyecto/grupo/ubicación;
- fecha ocurrida y fecha registrada;
- fuente y observaciones.

## Excepciones iniciales probadas

- DAMAGED;
- BURNED;
- MISSING;
- LOST;
- STOLEN;
- SEIZED;
- MAINTENANCE;
- HIBERNATED;
- NO_INFO.

Estos valores son semillas en catálogo. Pueden crearse otros estados y movimientos desde administración sin hardcodear ubicaciones ni tecnologías.

## Conciliación con herramientas previas

El diseño rescata principios ya validados en `Tendido-Diario-revision`:

- combinar fuentes SERCEL/INOVA/comentarios;
- conservar prioridad/procedencia de fuente;
- detectar cambios contra histórico;
- evitar correcciones manuales invisibles.

Alpha.3 todavía no reemplaza por completo los parsers especializados de esa herramienta; prepara el contrato de destino para integrar sus resultados sin duplicar identidades.
