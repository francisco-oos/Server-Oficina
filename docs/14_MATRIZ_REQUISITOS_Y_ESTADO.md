# 14 · Matriz de requisitos y estado

| Requisito acordado | Estado alpha.2 | Implementación / siguiente paso |
|---|---|---|
| Persona estable aunque cambie ID laboral | IMPLEMENTADO | `persons` + `employment_engagements` |
| Baja y recontratación | IMPLEMENTADO | API + eventos + pruebas |
| Outsourcing/renovaciones | BASE IMPLEMENTADA | `provider` + `contract_periods`; normalización de organizaciones queda futura |
| Proyectos | IMPLEMENTADO base | `projects`; cierre auditable se completa con Asset Core |
| Grupos/cuadrillas temporales | IMPLEMENTADO base | `work_groups` + `group_assignments` |
| Asistencia desde Excel/CSV | IMPLEMENTADO base | PREVIEW→COMMIT + SHA + issues |
| Buscar persona por nombre/ID | IMPLEMENTADO | directorio/API/UI |
| EPP solicitud vs validación RRHH | IMPLEMENTADO | RBAC + `epp_requests`/`epp_history` |
| Capacitación RRHH→HSE | IMPLEMENTADO base | vigencia/documentos en 0.2 |
| Casos/evidencia sin sanción automática | IMPLEMENTADO | permisos separados |
| `occurred_at` vs `recorded_at` | IMPLEMENTADO | `operational_events` |
| Auditoría | IMPLEMENTADO base | `audit_log` |
| Importación conserva original y hash | IMPLEMENTADO | `/srv/.../data/app/imports` en despliegue |
| Backend/frontend verificables por separado | IMPLEMENTADO en alpha.2 | scripts `verify-*` |
| Iniciar/detener/estado/logs simples | IMPLEMENTADO en alpha.2 | iniciadores raíz |
| PostgreSQL/Docker en `/srv` | IMPLEMENTADO despliegue alpha.2 | no usar PostgreSQL nativo en `/var` |
| Backup/restore | IMPLEMENTADO + infraestructura validada | gate integral de app pendiente |
| Localizar persona: grupo/responsable/unidad/radio/teléfono/campamento | PARCIAL | persona/grupo ya; resto entra por módulos temporales, sin duplicar |
| Control Material / Asset Core | DISEÑADO/INVESTIGADO | 0.3 |
| Vida útil/mantenimiento | DISEÑADO/INVESTIGADO | 0.3/0.4, con NodeHealth como fuente |
| Nodo TX/Taller/campo | DISEÑADO | 0.4; identidad de nodo = asset |
| HSE Campo PDF/JSON/QR | ADAPTADOR DISEÑADO | 0.5; conservar original + cifrado + hash |
| Transporte/checklist/km/combustible/fotos | DISEÑADO | 0.6 |
| Cierre de proyecto y transferencia de activos | DISEÑADO | Asset Core + conciliación |
| Captura de campo offline tipo Operación de Campo | FUTURO | reglas versionadas + cola offline/acuse; no depender de Telegram |

## Regla de avance

No marcar `IMPLEMENTADO` por tener sólo una tabla o una pantalla. El estado cambia cuando existen: contrato de datos + API/UI necesaria + pruebas + documentación + gate físico cuando corresponda.

## Evidencia y procedencia

La clasificación de fuentes y evidencia interna se mantiene en `docs/18_EVIDENCIA_OPERATIVA_Y_TRAZABILIDAD_DE_FUENTES.md` y `references/internal_evidence.json`. Ningún documento interno se empaqueta con datos sensibles.
