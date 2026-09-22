# 00 · Índice de documentación — Server Oficina 0.2.0-alpha.1 (candidato)

Este índice define el orden canónico de lectura. La documentación distingue
**implementado**, **validado**, **parcial** y **futuro**; una idea investigada no
se presenta como función terminada.

## Fundamentos

| Orden | Documento | Propósito |
|---:|---|---|
| 1 | `01_PROBLEMA_Y_FINALIDAD.md` | problema operativo, propósito y límites |
| 2 | `02_ARQUITECTURA.md` | arquitectura técnica vigente |
| 3 | `27_TRACKING_CORE.md` | **el núcleo común y sus invariantes** |
| 4 | `28_MODELO_DOMINIO_POR_AREA.md` | qué significa cada cosa en la operación |
| 5 | `06_MODELO_DATOS.md` | modelo de datos e invariantes |
| 6 | `29_AUTORIDAD_DATO_POR_AREA.md` | **quién manda sobre cada dato** |
| 7 | `03_DECISIONES_Y_RAZONAMIENTO.md` | ADR, razonamiento y descartes |


## Nube Local e inteligencia documental — norte 0.2

| Documento | Propósito |
|---|---|
| `38_MISION_VISION_NUBE_LOCAL_IA.md` | **misión, visión y principios no negociables** |
| `39_ARQUITECTURA_NUBE_LOCAL_GRAFO.md` | arquitectura local-first, planos de archivos/conocimiento y grafo |
| `40_SINCRONIZACION_CONFLICTOS_VERSIONADO.md` | leases, versiones, concurrencia y merge de tres vías |
| `41_INTELIGENCIA_DOCUMENTAL_APRENDIZAJE.md` | aprendizaje por reglas/aprobaciones, IA local y preguntas humanas |
| `42_PLAN_PRUEBAS_NUBE_LOCAL_24_CLIENTES.md` | gate automático y prueba física en Latitude |
| `43_ADR_NORTE_NUBE_LOCAL_GRAFO_IA.md` | decisiones formales para 0.2 |
| `44_INVESTIGACION_SINCRONIZACION_IA_GRAFOS.md` | investigación comparada y decisiones derivadas |

Estos documentos gobiernan la evolución 0.2. La implementación 0.1 permanece
como dominio probado debajo: no se reemplaza Tracking Core, se le añade una
capa local-first de documentos, versiones, aprendizaje y procedencia.

## Interfaz

| Orden | Documento | Propósito |
|---:|---|---|
| 8 | `31_ARQUITECTURA_UI_Y_NAVEGACION.md` | **navegación doble y fichas por dominio** |
| 9 | `30_DASHBOARD_CONFIGURABLE_Y_WIDGETS.md` | **vista resumen configurable y cómo crear widgets** |
| 10 | `26_UI_PROFESIONAL_Y_FLUJOS.md` | criterios de flujo cotidiano (antecedente) |
| 11 | `17_UI_RRHH_Y_FICHA_INTEGRAL.md` | ficha integral de personal (antecedente) |

## Desarrollo

| Orden | Documento | Propósito |
|---:|---|---|
| 12 | `33_GUIA_DESARROLLO_MULTIDESARROLLADOR.md` | **estructura, convenciones y cómo extender** |
| 13 | `32_API_REFERENCIA.md` | referencia de API por área |
| 14 | `22_RBAC_PERFILES_CONFIGURABLES.md` | perfiles dinámicos y permisos |
| 15 | `15_CONTRATOS_Y_GATES_MODULARES.md` | contratos entre módulos |
| 16 | `16_MONOREPO_BACKEND_FRONTEND_OPERACION.md` | separación lógica y operadores |
| 17 | `34_CONTRATO_INGESTA_DOCUMENTAL.md` | **contrato para el módulo de ingesta documental** |

## Dominios

| Orden | Documento | Propósito |
|---:|---|---|
| 18 | `19_ASSET_CORE_TRACKING_NODES.md` | activos, custodia y tracking de nodos |
| 19 | `20_TALLER_MANTENIMIENTO_VIDA_UTIL.md` | taller, partes, downtime, SOH/RUL |
| 20 | `21_EVIDENCIAS_NAS_Y_ORGANIZADOR.md` | NAS/SMB, upload e indexación |
| 21 | `09_FLUJO_IMPORTACION_OFICINA.md` | preview/commit y procedencia |
| 22 | `18_EVIDENCIA_OPERATIVA_Y_TRAZABILIDAD_DE_FUENTES.md` | procedencia y evidencia |

## Operación y calidad

| Orden | Documento | Propósito |
|---:|---|---|
| 23 | `07_INSTALACION_DEBIAN.md` | despliegue reproducible en Latitude |
| 24 | `24_ACTUALIZACION_Y_ROLLBACK_ALPHA2_ALPHA3.md` | actualización aditiva y rollback |
| 25 | `36_BACKUP_RESTORE.md` | **respaldo y restauración** |
| 26 | `35_TESTING_Y_RUNTIME.md` | **pruebas, gates y aislamiento del runtime** |
| 27 | `08_PLAN_PRUEBAS_Y_GATES.md` | validadores y QA |
| 28 | `23_PLAN_PRUEBAS_CASOS_USO_ALPHA3.md` | historias de aceptación |
| 29 | `14_MATRIZ_REQUISITOS_Y_ESTADO.md` | **requisito → estado real → prueba** |
| 30 | `11_ESTADO_REAL_LATITUDE_20260911.md` | hechos físicos verificados |
| 31 | `10_ROADMAP.md` | fases y criterio de cierre |

## Investigación y procedencia

| Orden | Documento | Propósito |
|---:|---|---|
| 32 | `04_REFERENCIAS_REPOSITORIOS.md` | repositorios estudiados y licencias |
| 33 | `05_DESCARTES.md` | alternativas evaluadas y no adoptadas |
| 34 | `12_INVESTIGACION_CICLO_VIDA_ACTIVOS.md` | investigación Asset Core / RUL |
| 35 | `13_INVESTIGACION_RRHH_OPERATIVO.md` | investigación RRHH operativo |
| 36 | `25_REVISION_HERRAMIENTAS_EXISTENTES.md` | patrones aprendidos de herramientas externas |

## Documentos raíz de entrega

`docs/INICIO_RAPIDO.md`, `README.md`, `CHANGELOG.md`, `reports/TEST_RESULTS.md`,
`SECURITY.md`, `NOTICE.md`, `BUILD_INFO.json` y `MANIFEST.sha256` forman la
ficha de una release. En `reports/` están los reportes PRE/POST, la matriz de
requisitos, el reporte de cambios de interfaz, el de seguridad y los pendientes
reales de esta entrega.

## Regla de gobierno

Una investigación sólo cambia el producto cuando la decisión queda promovida a
arquitectura/ADR y existe implementación verificable. Lo que no debe quedar
hardcodeado —ubicaciones, tecnologías, estados, tipos de activo, perfiles de
negocio, repositorios NAS y **ahora también la composición del dashboard**— se
modela como datos o configuración.
