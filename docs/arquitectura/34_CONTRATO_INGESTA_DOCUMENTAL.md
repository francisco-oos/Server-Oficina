# 34 · Contrato para el Módulo de Ingesta Documental por Área

Otro programador iniciará un **Módulo de Ingesta Documental por Área**,
comenzando por RRHH. Este documento fija los contratos para que se integre en
esta misma base y **no** nazca una segunda versión incompatible.

## Regla de integración

> No se crea un proyecto paralelo ni un modelo propio de lotes, incidencias o
> evidencias. El módulo se apoya en `ImportBatch`, `ImportIssue`,
> `EvidenceRepository`, `EvidenceRecord` y el Tracking Core existentes.

## Lo que ya existe y debe reutilizarse

### `ImportBatch` — el lote

| Campo | Significado |
|---|---|
| `kind` | tipo de ingesta. **El módulo añade sus propios valores**, p. ej. `hr_docs` |
| `original_name` | nombre del archivo tal como lo entregó la oficina |
| `stored_path` | copia íntegra del original conservada por el sistema |
| `sha256` | huella del original |
| `status` | `PREVIEW` → `COMMITTED` |
| `summary` | JSON libre con el resumen de la vista previa |
| `created_by` / `created_at` / `committed_at` | procedencia y tiempos |

### `ImportIssue` — lo que no encajó

| Campo | Significado |
|---|---|
| `batch_id` | lote al que pertenece |
| `row_number` | fila o página de origen, si aplica |
| `issue_type` | clasificación estable, en mayúsculas |
| `message` | texto en español dirigido al operador |
| `payload` | JSON con el dato crudo para poder reprocesar |
| `status` | `OPEN` / resuelto |

### `EvidenceRecord` — el documento en sí

Para documentos que quedan como archivo (contratos escaneados, constancias),
usar `EvidenceRepository` + `EvidenceRecord` y **no** una tabla nueva. Aporta ya
SHA-256, tamaño, MIME, repositorio LOCAL/SMB, indexación de archivos que ya
viven en NAS sin moverlos, y protección contra traversal.

## El ciclo obligatorio: PREVIEW → COMMIT

**Nada se escribe en el expediente hasta que una persona confirma.** Es la regla
que ya cumplen las importaciones de asistencia y de activos, y no es negociable.

```
POST /api/ingesta/{area}/preview     → crea ImportBatch(status=PREVIEW),
                                       conserva el original + SHA-256,
                                       genera ImportIssue por cada problema,
                                       devuelve batch_id + resumen. NO escribe.
GET  /api/ingesta/{batch_id}/issues  → incidencias para revisión humana
POST /api/ingesta/{batch_id}/commit  → aplica, marca COMMITTED, registra eventos
```

Un `commit` sobre un lote ya confirmado debe responder **409**, no reprocesar.

## Contratos que el módulo debe respetar

1. **Persona ≠ contratación.** Un documento se asocia a `person_id`. Si trae un
   ID laboral, se resuelve a la persona; jamás se crea una persona nueva porque
   el ID laboral cambió.
2. **Nunca se crea una identidad sin decisión humana.** Una fila que no case con
   nadie es un `ImportIssue`, no un alta automática.
3. **Ocurrió ≠ se registró.** La fecha del documento es `occurred_at`; la de
   ingesta es `recorded_at`.
4. **Procedencia siempre.** Los eventos que genere el módulo llevan
   `source_type="IMPORT"` y `source_id=<batch_id>`, para poder responder de
   dónde salió cada dato.
5. **Evidencia ≠ sanción.** Un documento de incidencia se registra como hecho;
   quien resuelve es el área con autoridad.
6. **Autoridad por área.** Un documento de RRHH lo confirma RRHH. Ver
   `docs/29_AUTORIDAD_DATO_POR_AREA.md`.
7. **Sólo tablas nuevas.** Si necesita persistencia propia, agrega tablas; no
   añade columnas a tablas existentes (ver doc 33).

## Permisos

Reutilizar lo que ya existe y añadir sólo lo que falte:

```python
"imports.commit"        # ya existe: confirmar una ingesta
"docs.ingest"           # nuevo sugerido: cargar documentos para vista previa
"docs.view"             # nuevo sugerido: consultar documentos ingeridos
```

Declarar el dominio en `DATA_DOMAINS` (`app/core/areas.py`) con RRHH como
autoridad para el corte inicial.

## Integración con la interfaz

- Vista nueva en `app/static/app.js`, registrada en `VIEWS` y en `NAV` bajo su
  área, con su permiso.
- Los documentos de una persona deben aparecer en la pestaña **Evidencias** de
  su expediente: basta registrarlos con `entity_type="PERSON"` y
  `entity_id=<person_id>`.
- Si el módulo aporta indicadores (documentos pendientes de revisión, lotes con
  incidencias abiertas), se registran como **widgets** (doc 30) y quedan
  disponibles en el modo DEV sin tocar el dashboard.

## Lo que el módulo NO debe hacer

- Crear su propia tabla de personas, activos o evidencias.
- Escribir directamente en el expediente sin pasar por PREVIEW → COMMIT.
- Deducir bajas, sanciones o resoluciones a partir de un documento.
- Hardcodear rutas de NAS, campamentos o nombres de empresa.
- Guardar credenciales de acceso a repositorios en PostgreSQL.

## Punto de contacto

Si el módulo necesita algo que estos contratos no permiten, la vía es proponer
un ADR en `docs/03_DECISIONES_Y_RAZONAMIENTO.md`, no divergir del modelo.
