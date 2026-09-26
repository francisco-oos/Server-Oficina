# Índice de documentación — Server Oficina

Este índice es el punto de entrada autoritativo. La documentación se organiza por
responsabilidad para que la raíz de `docs/` permanezca pequeña y navegable.

## Norte y visión

- `vision/01_PROBLEMA_Y_FINALIDAD.md` — problema que resuelve Server Oficina.
- `vision/38_MISION_VISION_NUBE_LOCAL_IA.md` — misión, visión y principios no negociables.
- `vision/10_ROADMAP.md` — fases y criterios de cierre.

## Arquitectura

- `arquitectura/02_ARQUITECTURA.md`
- `arquitectura/06_MODELO_DATOS.md`
- `arquitectura/27_TRACKING_CORE.md`
- `arquitectura/28_MODELO_DOMINIO_POR_AREA.md`
- `arquitectura/29_AUTORIDAD_DATO_POR_AREA.md`
- `arquitectura/34_CONTRATO_INGESTA_DOCUMENTAL.md`
- `arquitectura/39_ARQUITECTURA_NUBE_LOCAL_GRAFO.md`
- `arquitectura/40_SINCRONIZACION_CONFLICTOS_VERSIONADO.md`
- `arquitectura/41_INTELIGENCIA_DOCUMENTAL_APRENDIZAJE.md`
- `arquitectura/15_CONTRATOS_Y_GATES_MODULARES.md`
- `arquitectura/16_MONOREPO_BACKEND_FRONTEND_OPERACION.md`
- `arquitectura/18_EVIDENCIA_OPERATIVA_Y_TRAZABILIDAD_DE_FUENTES.md`

## Decisiones

- `decisiones/03_DECISIONES_Y_RAZONAMIENTO.md`
- `decisiones/05_DESCARTES.md`
- `decisiones/43_ADR_NORTE_NUBE_LOCAL_GRAFO_IA.md`
- `decisiones/48_ADR_ALMACENAMIENTO_JERARQUICO_Y_DOMAIN_PACKS.md`

## Investigación

- `investigacion/04_REFERENCIAS_REPOSITORIOS.md`
- `investigacion/12_INVESTIGACION_CICLO_VIDA_ACTIVOS.md`
- `investigacion/13_INVESTIGACION_RRHH_OPERATIVO.md`
- `investigacion/25_REVISION_HERRAMIENTAS_EXISTENTES.md`
- `investigacion/44_INVESTIGACION_SINCRONIZACION_IA_GRAFOS.md`
- `investigacion/46_INVESTIGACION_SINCRONIZACION_ROBUSTA.md`
- `investigacion/47_ALMACENAMIENTO_JERARQUICO_ARCHIVOS_GRANDES.md`

## Dominios actuales

- `dominios/09_FLUJO_IMPORTACION_OFICINA.md`
- `dominios/19_ASSET_CORE_TRACKING_NODES.md`
- `dominios/20_TALLER_MANTENIMIENTO_VIDA_UTIL.md`
- `dominios/21_EVIDENCIAS_NAS_Y_ORGANIZADOR.md`

## Interfaz

- `interfaz/17_UI_RRHH_Y_FICHA_INTEGRAL.md`
- `interfaz/26_UI_PROFESIONAL_Y_FLUJOS.md`
- `interfaz/30_DASHBOARD_CONFIGURABLE_Y_WIDGETS.md`
- `interfaz/31_ARQUITECTURA_UI_Y_NAVEGACION.md`

## Seguridad

- `seguridad/22_RBAC_PERFILES_CONFIGURABLES.md`

## Pruebas

- `pruebas/08_PLAN_PRUEBAS_Y_GATES.md`
- `pruebas/23_PLAN_PRUEBAS_CASOS_USO_ALPHA3.md`
- `pruebas/35_TESTING_Y_RUNTIME.md`
- `pruebas/42_PLAN_PRUEBAS_NUBE_LOCAL_24_CLIENTES.md`

## Operación

- `operacion/07_INSTALACION_DEBIAN.md`
- `operacion/11_ESTADO_REAL_LATITUDE_20260911.md`
- `operacion/24_ACTUALIZACION_Y_ROLLBACK_ALPHA2_ALPHA3.md`
- `operacion/36_BACKUP_RESTORE.md`
- `operacion/45_FASE_1_SINCRONIZACION_PC_LATITUDE.md`

## Desarrollo

- `desarrollo/32_API_REFERENCIA.md`
- `desarrollo/33_GUIA_DESARROLLO_MULTIDESARROLLADOR.md`

## Estado y relevo

- `estado/14_MATRIZ_REQUISITOS_Y_ESTADO.md`
- `estado/37_RELEVO_OPENAI_ALPHA4_R1.md`
- `../reports/PENDIENTES_REALES.md`

## Regla de gobierno

Una investigación no se convierte en arquitectura sólo por ser interesante:
debe quedar promovida mediante ADR, contrato, implementación verificable y
pruebas. La sincronización, la inteligencia documental y los dominios se
mantienen desacoplados para que el núcleo pueda reutilizarse en otras oficinas.
