# 00 · LEEME PRIMERO — Server Oficina 0.1.0-alpha.4

Esta entrega continúa **la misma base** instalada como `0.1.0-alpha.3` en
`server-oficina`. No crea un proyecto paralelo, no sustituye FastAPI/PostgreSQL,
no rehace el dominio y no crea una interfaz aparte.

## Qué es esta versión

Una revisión, corrección y evolución centrada en **cerrar la brecha entre lo que
el sistema modela y lo que la interfaz presentaba**, más tres requisitos que
faltaban por completo.

### Lo nuevo

1. **Vista resumen configurable.** 28 widgets registrados en código y 7
   dashboards (general + uno por área) administrables desde un modo DEV. Las
   tarjetas dejaron de estar hardcodeadas.
2. **Dominio de Transporte.** Unidades, conductores, asignaciones temporales,
   radio y teléfono asociados, disponibilidad, checklist e incidencias.
3. **Autoridad sobre el dato por área.** 15 dominios de información con
   autoridad, consulta, propuesta y confirmación declaradas.
4. **Interfaz reconstruida.** Navegación por área **y** transversal, cuatro
   fichas específicas por dominio, y diseño responsive real.
5. **Corregido el `PermissionError`** al validar a mano una release instalada.

### La idea que gobierna el trabajo

> El error que se corrige es interpretar «todo tiene trazabilidad» como «todo
> debe tener la misma interfaz». Tracking Core es común por debajo, pero RRHH
> sigue la vida laboral de una persona, Operación el ciclo de un nodo, Material
> la custodia, Transporte las unidades y Taller el diagnóstico. Todos se
> relacionan y forman una historia común, pero **sus fichas, acciones, estados y
> timelines no son intercambiables**.

## Reglas que no deben romperse

1. **Persona ≠ contratación.** Una recontratación conserva `person_id`.
2. **Activo ≠ proyecto.** Serie, IMEI, QR e identidad sobreviven a las transferencias.
3. **Estado actual ≠ historial.** Toda transición genera movimiento o evento.
4. **Ocurrió ≠ se registró.** Se conservan `occurred_at` y `recorded_at`.
5. **Predicción ≠ hecho.** SOH/RUL no retira equipos automáticamente.
6. **Evidencia ≠ sanción.** El área competente resuelve.
7. **Faltante de inventario ≠ pérdida definitiva.**
8. **Nada operacional atado a un campamento.** Ubicaciones, tipos, tecnologías y
   estados se configuran en base de datos.
9. **NAS fail-closed.** Si el repositorio SMB deja de estar montado, la carga se
   rechaza en vez de caer a disco local.
10. **Credenciales SMB fuera de PostgreSQL**, root-only en `/etc/server-oficina`.
11. **Sólo se agregan tablas.** Ninguna tabla existente cambia de forma.
12. **No crear otro proyecto.**

## Orden recomendado de lectura

```text
 1. 00_LEEME_PRIMERO.md            (este archivo)
 2. docs/00_INDICE_DOCUMENTACION.md
 3. docs/27_TRACKING_CORE.md       el núcleo común y sus invariantes
 4. docs/29_AUTORIDAD_DATO_POR_AREA.md   quién manda sobre cada dato
 5. docs/31_ARQUITECTURA_UI_Y_NAVEGACION.md
 6. docs/30_DASHBOARD_CONFIGURABLE_Y_WIDGETS.md
 7. docs/33_GUIA_DESARROLLO_MULTIDESARROLLADOR.md   ← si va a programar
 8. docs/14_MATRIZ_REQUISITOS_Y_ESTADO.md           estado real de cada requisito
 9. reports/PENDIENTES_REALES.md                    lo que NO está terminado
10. VALIDAR_SERVER_OFICINA.sh
11. INSTALAR_EN_TABLETA.sh
```

Si desarrolla el **Módulo de Ingesta Documental**, lea además
`docs/34_CONTRATO_INGESTA_DOCUMENTAL.md` antes de escribir una línea.

## Iniciadores principales

- `INICIAR_SERVER_OFICINA.sh` · `DETENER_SERVER_OFICINA.sh` · `REINICIAR_SERVER_OFICINA.sh`
- `ESTADO_SERVER_OFICINA.sh` · `LOGS_SERVER_OFICINA.sh` · `ABRIR_SERVER_OFICINA.sh`
- `BACKUP_SERVER_OFICINA.sh` · `RESTORE_SERVER_OFICINA.sh`
- `VALIDAR_SERVER_OFICINA.sh` · `VALIDAR_BACKEND.sh` · `VALIDAR_FRONTEND.sh`
  · `VALIDAR_FRONTEND_E2E.sh` · `VALIDAR_DESPLIEGUE.sh`
- `INSTALAR_EN_TABLETA.sh` · `INSTALAR_ACCESO_ESCRITORIO.sh`
- `CONFIGURAR_NAS_EVIDENCIAS.sh` · `CONFIGURAR_BANDEJA_EVIDENCIAS.sh`
- `GENERAR_MANIFEST.sh`

## Actualización desde alpha.3

Aditiva. Se agregan **6 tablas** y no cambia ninguna existente, de modo que
`Base.metadata.create_all` promueve la instalación real sin migración manual.
El instalador conserva el backup pre-upgrade y el rollback de release.

## Estado de entrega

Esta versión se considera **alpha** aunque los 6 gates automáticos pasen,
incluido el recorrido de navegador. La promoción a estable exige cerrar los
gates físicos de la Latitude listados en `reports/PENDIENTES_REALES.md`:
actualización real, NAS real, archivos reales de oficina, pruebas multiusuario,
respaldo y restauración completos, estabilidad prolongada y **la revisión visual
del usuario**, que es imprescindible porque la interfaz se rehízo por completo.

Nada se declara terminado por compilar ni por tener los gates en verde.
