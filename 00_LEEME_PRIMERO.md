# 00 · LEEME PRIMERO — Server Oficina 0.1.0-alpha.3

Esta entrega continúa **la misma base** instalada como `0.1.0-alpha.2` en `server-oficina`. No crea un proyecto paralelo, no sustituye Tracking Core y no vuelve a instalar PostgreSQL nativo.

## Qué incorpora alpha.3

`alpha.3` amplía el corte Oficina/Personal con una base operativa real para **Material + Tracking Nodes + Taller + Inventario + Evidencias**, manteniendo FastAPI + UI web estática + PostgreSQL 18.6.

- perfiles/roles personalizados con matriz de permisos;
- catálogos operativos editables: ubicaciones, estados, movimientos, resultados, asistencia, eventos laborales, etc.;
- RRHH: categoría, licencia/vigencia, rotación trabajo/descanso, asignación a proyecto/grupo/ubicación/supervisor/unidad, asistencia manual, renuncia/despido/fin de contrato y recontratación;
- empresas/outsourcing normalizables sin eliminar el texto histórico `provider` heredado;
- Asset Core: tipo configurable, tecnología, serie, IMEI, QR, número económico y otros identificadores;
- custodia y movimientos con historial, sin sustituir el pasado por un único estado;
- Tracking Nodes por operación/lote: tendido, rotación, levantado, retorno y excepciones;
- estados cubiertos en pruebas: dañado, quemado, no encontrado, extraviado, robado, incautado, mantenimiento, hibernado y retorno sin información;
- Taller: orden, diagnóstico, reparación, piezas, serial retirado/instalado, resultado y downtime;
- observaciones de salud/RUL con procedencia; nunca provocan una baja automática;
- inventario físico y lista de faltantes sin convertir automáticamente una discrepancia en pérdida definitiva;
- cierre de proyecto con snapshot auditable de estados, excepciones y material transferible;
- evidencias en repositorios LOCAL/SMB configurables, hashes SHA-256 y registro de archivos que ya existen en NAS;
- UI reorganizada en Operación / Oficina / Administración;
- actualización con backup pre-upgrade y rollback de release si falla `/api/health`.

## Reglas que no deben romperse

1. **Persona ≠ contratación.** Una recontratación conserva `person_id`.
2. **Activo ≠ proyecto.** Serie/IMEI/QR/identidad sobreviven a cambios de proyecto.
3. **Estado actual ≠ historial.** Toda transición relevante genera movimiento/evento.
4. **Ocurrió ≠ se registró.** Se conservan `occurred_at` y `recorded_at`.
5. **Predicción ≠ hecho.** SOH/RUL/health score no retiran equipos automáticamente.
6. **Evidencia ≠ sanción.** RRHH/jefatura resuelve; el sistema conserva hechos y fuentes.
7. **Nada operacional se amarra a un campamento concreto.** Ubicaciones, tipos, tecnologías y estados se configuran en BD.
8. **NAS fail-closed.** Si un repositorio SMB deja de estar montado, la carga se rechaza en vez de caer silenciosamente a disco local.
9. **Credenciales SMB fuera de PostgreSQL.** Se guardan root-only en `/etc/server-oficina`.
10. **No copiar productos externos.** Snipe-IT/GLPI/Ralph/OpenBoxes sirven como estudio de patrones; Server Oficina conserva arquitectura y dominio propios.

## Orden recomendado

```text
1. 00_LEEME_PRIMERO.md
2. docs/00_INDICE_DOCUMENTACION.md
3. docs/02_ARQUITECTURA.md
4. docs/03_DECISIONES_Y_RAZONAMIENTO.md
5. docs/06_MODELO_DATOS.md
6. docs/19_ASSET_CORE_TRACKING_NODES.md
7. docs/20_TALLER_MANTENIMIENTO_VIDA_UTIL.md
8. docs/21_EVIDENCIAS_NAS_Y_ORGANIZADOR.md
9. docs/22_RBAC_PERFILES_CONFIGURABLES.md
10. docs/23_PLAN_PRUEBAS_CASOS_USO_ALPHA3.md
11. docs/24_ACTUALIZACION_Y_ROLLBACK_ALPHA2_ALPHA3.md
12. docs/25_REVISION_HERRAMIENTAS_EXISTENTES.md
13. docs/26_UI_PROFESIONAL_Y_FLUJOS.md
14. VALIDAR_SERVER_OFICINA.sh
15. INSTALAR_EN_TABLETA.sh
```

## Iniciadores principales

- `INICIAR_SERVER_OFICINA.sh`
- `DETENER_SERVER_OFICINA.sh`
- `REINICIAR_SERVER_OFICINA.sh`
- `ESTADO_SERVER_OFICINA.sh`
- `LOGS_SERVER_OFICINA.sh`
- `ABRIR_SERVER_OFICINA.sh`
- `BACKUP_SERVER_OFICINA.sh`
- `RESTORE_SERVER_OFICINA.sh`
- `VALIDAR_SERVER_OFICINA.sh`
- `VALIDAR_BACKEND.sh`
- `VALIDAR_FRONTEND.sh`
- `VALIDAR_FRONTEND_E2E.sh`
- `VALIDAR_DESPLIEGUE.sh`
- `INSTALAR_EN_TABLETA.sh`
- `CONFIGURAR_NAS_EVIDENCIAS.sh`
- `CONFIGURAR_BANDEJA_EVIDENCIAS.sh`

## Estado de entrega

Esta versión se considera **alpha** aunque los gates automáticos pasen. La promoción a estable requiere validación prolongada con datos reales, concurrencia, NAS real, backups restaurados y recorridos de navegador en la Latitude.
