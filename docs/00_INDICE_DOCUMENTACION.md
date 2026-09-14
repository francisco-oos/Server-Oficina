# 00 · Índice de documentación — Server Oficina 0.1.0-alpha.2

Este índice define el orden canónico de lectura. La documentación describe **estado real**, decisiones, descartes, investigación y roadmap; no debe presentarse una función como implementada sólo porque esté diseñada.

| Orden | Documento | Propósito |
|---:|---|---|
| 1 | `01_PROBLEMA_Y_FINALIDAD.md` | problema operativo, propósito y límites |
| 2 | `02_ARQUITECTURA.md` | arquitectura técnica vigente |
| 3 | `03_DECISIONES_Y_RAZONAMIENTO.md` | ADR/razonamiento y por qué se eligió cada camino |
| 4 | `04_REFERENCIAS_REPOSITORIOS.md` | repositorios estudiados, procedencia y límites de reutilización |
| 5 | `05_DESCARTES.md` | alternativas evaluadas y no adoptadas |
| 6 | `06_MODELO_DATOS.md` | modelo vigente y fronteras de evolución |
| 7 | `07_INSTALACION_DEBIAN.md` | instalación/despliegue reproducible en la Latitude |
| 8 | `08_PLAN_PRUEBAS_Y_GATES.md` | validadores, gates y estado de QA |
| 9 | `09_FLUJO_IMPORTACION_OFICINA.md` | preview/commit, procedencia y ambigüedad de importaciones |
| 10 | `10_ROADMAP.md` | fases y criterio de cierre por módulo |
| 11 | `11_ESTADO_REAL_LATITUDE_20260911.md` | infraestructura física ya preparada y límites actuales |
| 12 | `12_INVESTIGACION_CICLO_VIDA_ACTIVOS.md` | Asset Core, condición, mantenimiento, RUL y nodos |
| 13 | `13_INVESTIGACION_RRHH_OPERATIVO.md` | persona/empleo, roster, EPP, capacitación y privacidad |
| 14 | `14_MATRIZ_REQUISITOS_Y_ESTADO.md` | acuerdo → estado IMPLEMENTED/PARTIAL/DESIGNED/FUTURE |
| 15 | `15_CONTRATOS_Y_GATES_MODULARES.md` | contratos entre módulos/fuentes y Definition of Done |
| 16 | `16_MONOREPO_BACKEND_FRONTEND_OPERACION.md` | cómo se divide lógicamente backend/frontend/operación |
| 17 | `17_UI_RRHH_Y_FICHA_INTEGRAL.md` | rescate de UX del prototipo previo sin datos demo |
| 18 | `18_EVIDENCIA_OPERATIVA_Y_TRAZABILIDAD_DE_FUENTES.md` | evidencia propia, referencias y reglas de procedencia |

## Documentos raíz de entrega

- `00_LEEME_PRIMERO.md`: puerta de entrada.
- `README.md`: resumen técnico/operativo.
- `CHANGELOG.md`: cambios por versión.
- `TEST_RESULTS.md`: resultados verificables y gates bloqueados.
- `SECURITY.md`: seguridad, exposición y manejo de secretos.
- `NOTICE.md`: avisos y política de referencias.
- `BUILD_INFO.json`: metadatos exactos de construcción.
- `MANIFEST.sha256`: integridad de los archivos empaquetados.

## Regla de gobierno

Si un documento de investigación propone algo que contradice una decisión consolidada de arquitectura/alcance, **no modifica el sistema por sí solo**. Debe promoverse a decisión explícita y quedar documentado en `03_DECISIONES_Y_RAZONAMIENTO.md` antes de cambiar código o esquema.
