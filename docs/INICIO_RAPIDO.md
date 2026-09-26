# LEEME PRIMERO — Server Oficina 0.2 candidato

Server Oficina evoluciona la misma base instalada en `server-oficina`. No crea
un producto paralelo ni sustituye FastAPI/PostgreSQL/Tracking Core.

## Norte actual

Primero se cierra la infraestructura de archivos:

```text
PCs Windows ⇄ LAN ⇄ Latitude + SSD
                    ├─ sincronización
                    ├─ identidad de PC/usuario
                    ├─ versiones y conflictos
                    ├─ historial por SHA-256
                    └─ réplica NAS posterior
```

Sólo después se habilitan lectores/LLM por área.

## Reglas que no deben romperse

1. Persona, contratación y sesión de computadora son conceptos distintos.
2. El estado digital de una estación complementa a RRHH; no lo sustituye.
3. Archivo canónico; base derivada; evidencia navegable.
4. Un conflicto conserva las dos versiones antes de intentar resolverlo.
5. No hay merge binario ciego de Office.
6. NAS e Internet no deben ser requisito para el trabajo local ordinario.
7. La IA interpreta; PostgreSQL/Tracking Core conservan conocimiento verificable.
8. El aprendizaje de la LLM no se hardcodea al núcleo.
9. Todo conocimiento específico de una oficina debe poder vivir como
   configuración, reglas aprobadas o paquetes de dominio.
10. Nada se declara productivo sólo porque CI esté verde: requiere gate físico.

## Orden recomendado

1. `docs/00_INDICE_DOCUMENTACION.md`
2. `docs/vision/38_MISION_VISION_NUBE_LOCAL_IA.md`
3. `docs/arquitectura/27_TRACKING_CORE.md`
4. `docs/arquitectura/39_ARQUITECTURA_NUBE_LOCAL_GRAFO.md`
5. `docs/arquitectura/40_SINCRONIZACION_CONFLICTOS_VERSIONADO.md`
6. `docs/investigacion/46_INVESTIGACION_SINCRONIZACION_ROBUSTA.md`
7. `docs/investigacion/47_ALMACENAMIENTO_JERARQUICO_ARCHIVOS_GRANDES.md`
8. `docs/decisiones/48_ADR_ALMACENAMIENTO_JERARQUICO_Y_DOMAIN_PACKS.md`
9. `docs/estado/14_MATRIZ_REQUISITOS_Y_ESTADO.md`
10. `reports/PENDIENTES_REALES.md`

Para desarrollar, lea `docs/desarrollo/33_GUIA_DESARROLLO_MULTIDESARROLLADOR.md`.

## Gate vigente

La rama de sincronización permanece candidata hasta probar en hardware real:
1 PC + Latitude, después 2 y 5 PCs; cambio de Wi-Fi/DHCP; Internet apagado;
edición simultánea Office; borrado/restauración; reinicios; sesión humana y
recuperación integral.
