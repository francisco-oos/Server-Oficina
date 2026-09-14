# 14 · Matriz de requisitos y estado — alpha.3

| Requisito acordado | Estado | Evidencia alpha.3 |
|---|---|---|
| Persona estable aunque cambie ID laboral | IMPLEMENTADO/PROBADO | person + engagements + rehire |
| Renuncia/despido/rehire | IMPLEMENTADO/PROBADO | lifecycle events + suite |
| Outsourcing/empresa normalizados | IMPLEMENTADO BASE/PROBADO | organizations + engagement links; `provider` legado compatible |
| Categoría/licencia/vigencia/rotación | IMPLEMENTADO/PROBADO | `person_hr_profiles` |
| Asistencia | IMPLEMENTADO/PROBADO | manual + importación heredada |
| Cursos/EPP/casos | IMPLEMENTADO/PROBADO | flujos heredados + suite |
| Proyectos/grupos/ubicaciones configurables | IMPLEMENTADO/PROBADO | sin campamentos hardcodeados |
| Perfiles creados por administrador | IMPLEMENTADO/PROBADO | role↔permission dinámico |
| Tipos/tecnologías futuras sin editar código | IMPLEMENTADO/PROBADO | capacidades + tecnología configurable |
| Alta de radios/teléfonos/PC/drones/vehículos/nodos | IMPLEMENTADO/PROBADO | Asset Core |
| Serie/IMEI/QR/económico | IMPLEMENTADO/PROBADO | asset_identifiers |
| Custodia/asignación/localizador | IMPLEMENTADO/PROBADO | custody + assignment + `/locate` |
| Tendido/rotación/levantado/retorno | IMPLEMENTADO/PROBADO | node operations por lote |
| Quemado/incautado/perdido/robado/no encontrado/etc. | IMPLEMENTADO/PROBADO | resultado→movimiento por catálogo |
| Taller/mantenimiento/piezas/downtime | IMPLEMENTADO/PROBADO | maintenance orders/parts |
| SOH/RUL sin baja automática | IMPLEMENTADO/PROBADO | health observations |
| Inventario físico y material faltante | IMPLEMENTADO/PROBADO | inventory sessions/counts |
| Carga masiva de activos + metadata adicional | IMPLEMENTADO/PROBADO | preview/commit CSV |
| Cierre de proyecto auditable | IMPLEMENTADO/PROBADO | project_closeouts snapshot |
| Transferencia posterior conserva corte previo | IMPLEMENTADO/PROBADO | prueba de snapshot inmutable |
| Evidencia upload a repositorio | IMPLEMENTADO/PROBADO | SHA-256 + relación |
| Evidencia ya copiada por Windows/NAS | IMPLEMENTADO/PROBADO | register-existing sin mover original |
| SMB fail-closed | IMPLEMENTADO/PROBADO | 503 si mount ausente |
| Credenciales NAS fuera de BD | IMPLEMENTADO DEPLOY | root-only `/etc/server-oficina` |
| UI profesional por dominios | IMPLEMENTADO BASE | navegación Operación/Oficina/Admin |
| Backend/frontend/deploy verificables por separado | IMPLEMENTADO | validadores raíz/scripts |
| Backup pre-upgrade y rollback release | IMPLEMENTADO CONTRACT | installer alpha.3; gate físico pendiente al actualizar |
| SERCEL/INOVA parser avanzado | PARCIAL | destino preparado; adaptadores especializados posteriores |
| HSE Campo PDF/JSON/QR | DISEÑADO COMO ADAPTADOR | no duplicar evidencia original |
| Transporte checklist/km/combustible | FUTURO | Asset Core ya modela unidad/custodia |
| Captura offline tipo Operación de Campo | FUTURO | store-and-forward/reglas versionadas |

## Regla

`IMPLEMENTADO/PROBADO` significa contrato de datos + API/regla necesaria + prueba automática. Un gate físico se declara aparte cuando dependa de la Latitude/NAS/navegador real.
