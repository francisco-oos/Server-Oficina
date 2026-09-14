# 00 · Índice de documentación — Server Oficina 0.1.0-alpha.3

Este índice define el orden canónico de lectura. La documentación distingue **implementado**, **validado**, **parcial** y **futuro**; una idea investigada no se presenta como función terminada.

| Orden | Documento | Propósito |
|---:|---|---|
| 1 | `01_PROBLEMA_Y_FINALIDAD.md` | problema operativo, propósito y límites |
| 2 | `02_ARQUITECTURA.md` | arquitectura técnica vigente |
| 3 | `03_DECISIONES_Y_RAZONAMIENTO.md` | ADR/razonamiento y descartes |
| 4 | `04_REFERENCIAS_REPOSITORIOS.md` | repositorios estudiados, procedencia y licencias |
| 5 | `05_DESCARTES.md` | alternativas evaluadas y no adoptadas |
| 6 | `06_MODELO_DATOS.md` | modelo vigente e invariantes |
| 7 | `07_INSTALACION_DEBIAN.md` | despliegue reproducible en Latitude |
| 8 | `08_PLAN_PRUEBAS_Y_GATES.md` | validadores, gates y QA |
| 9 | `09_FLUJO_IMPORTACION_OFICINA.md` | preview/commit y procedencia |
| 10 | `10_ROADMAP.md` | fases y criterio de cierre |
| 11 | `11_ESTADO_REAL_LATITUDE_20260911.md` | hechos físicos verificados |
| 12 | `12_INVESTIGACION_CICLO_VIDA_ACTIVOS.md` | investigación Asset Core/condición/RUL |
| 13 | `13_INVESTIGACION_RRHH_OPERATIVO.md` | investigación RRHH operativo |
| 14 | `14_MATRIZ_REQUISITOS_Y_ESTADO.md` | requisito → estado real |
| 15 | `15_CONTRATOS_Y_GATES_MODULARES.md` | contratos entre módulos/fuentes |
| 16 | `16_MONOREPO_BACKEND_FRONTEND_OPERACION.md` | separación lógica y operadores |
| 17 | `17_UI_RRHH_Y_FICHA_INTEGRAL.md` | ficha integral de personal |
| 18 | `18_EVIDENCIA_OPERATIVA_Y_TRAZABILIDAD_DE_FUENTES.md` | procedencia/evidencia |
| 19 | `19_ASSET_CORE_TRACKING_NODES.md` | activos, custodia y tracking de nodos |
| 20 | `20_TALLER_MANTENIMIENTO_VIDA_UTIL.md` | taller, partes, downtime, SOH/RUL |
| 21 | `21_EVIDENCIAS_NAS_Y_ORGANIZADOR.md` | NAS/SMB, upload e indexación de existentes |
| 22 | `22_RBAC_PERFILES_CONFIGURABLES.md` | perfiles dinámicos y permisos |
| 23 | `23_PLAN_PRUEBAS_CASOS_USO_ALPHA3.md` | historias de aceptación alpha.3 |
| 24 | `24_ACTUALIZACION_Y_ROLLBACK_ALPHA2_ALPHA3.md` | actualización aditiva y rollback |
| 25 | `25_REVISION_HERRAMIENTAS_EXISTENTES.md` | patrones aprendidos de herramientas externas |
| 26 | `26_UI_PROFESIONAL_Y_FLUJOS.md` | arquitectura de navegación/UI |

## Documentos raíz de entrega

`00_LEEME_PRIMERO.md`, `README.md`, `CHANGELOG.md`, `TEST_RESULTS.md`, `SECURITY.md`, `NOTICE.md`, `BUILD_INFO.json` y `MANIFEST.sha256` forman la ficha de una release.

## Regla de gobierno

Una investigación sólo cambia el producto cuando la decisión queda promovida a arquitectura/ADR y existe implementación verificable. Los caminos que no deben quedar hardcodeados —ubicaciones, tecnologías, estados, tipos de activo, perfiles de negocio o repositorios NAS— se modelan como datos/configuración.
