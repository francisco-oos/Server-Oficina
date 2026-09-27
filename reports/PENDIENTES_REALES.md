# Pendientes reales

Lo que **no** está terminado. Esta release sigue siendo **alpha** aunque todos
los gates automáticos pasen.

## Revisión OpenAI R1 · pendientes adicionales

- **Autoridad HSE/casos:** la matriz declara HSE como autoridad de incidencias
  HSE, pero `CaseRecord` todavía no identifica el área propietaria y
  `cases.resolve` es global. Debe modelarse autoridad por caso antes de
  conceder resolución global a HSE.
- **Administración de perfiles/usuarios:** el backend ya permite editar perfiles
  personalizados y reasignar perfiles de usuarios; OpenAI R1 agrega la interfaz
  que faltaba para usar esas capacidades.

## Parcial: funciona con límite declarado

| # | Qué | Qué falta exactamente |
|---|---|---|
| 1 | **Rotación trabajo/descanso** | Se capturan y se muestran los días (21×7). No se genera calendario ni se proyecta quién está de descanso en una fecha futura. El widget «Personal en descanso» lee la asistencia del día, no la rotación. |
| 2 | **Fotografías en el checklist de transporte** | Se pueden adjuntar como evidencias del activo. No hay captura de foto integrada en el formulario de checklist ni miniaturas en la ficha. |
| 3 | **Observaciones sobre la persona** | Existen notas en casos y `metadata_json` en la ficha laboral. No hay bitácora de observaciones con su propia pantalla e historial. |
| 4 | **«Entregado» como cierre de taller** | Se representa con `MAINTENANCE_OUT` más el movimiento de custodia. No hay acuse de entrega firmado ni constancia imprimible. |
| 5 | **Reordenar widgets con arrastrar y soltar** | Se reordena con botones ▲▼, que funcionan bien con guantes. No hay drag & drop. |
| 6 | **Paginación de listados** | Hay límites duros (100–300 filas). Con inventarios de varios miles de activos hará falta paginar de verdad. |

## Pendiente: no implementado

| # | Qué | Por qué no entró |
|---|---|---|
| 7 | **Módulo de Ingesta Documental por Área** | Lo desarrollará otro programador. Esta entrega deja los **contratos** listos en `docs/arquitectura/34_CONTRATO_INGESTA_DOCUMENTAL.md` para que se integre con `ImportBatch`/`ImportIssue` y no nazca una versión incompatible. |
| 8 | **Herramienta de migraciones** | Mientras se respete «sólo se agregan tablas» no hace falta. Será necesaria en cuanto haya que alterar una columna con datos en producción. |
| 9 | **Exportaciones e informes imprimibles** | No estaban en el encargo. Se mencionan porque la oficina acabará pidiéndolos. |

## Gates físicos pendientes en la Latitude

Ninguno de estos puede cerrarse desde un entorno de construcción. Requieren el
equipo real.

| # | Gate | Cómo cerrarlo |
|---|---|---|
| 10 | Actualización `alpha.3 → alpha.4` sobre la instalación real | `./INSTALAR_EN_TABLETA.sh`, verificando el backup pre-upgrade y que `create_all` añade las 6 tablas nuevas sin tocar las existentes |
| 11 | Rollback controlado de release | forzar un fallo de `/api/health` y comprobar que el symlink `current` revierte |
| 12 | E2E de navegador **en la Latitude** | el recorrido pasa en este entorno; falta ejecutarlo en el hardware y resolución reales |
| 13 | Repositorio SMB/NAS real | montar el NAS de la oficina, cargar evidencia real y comprobar el comportamiento fail-closed desmontándolo |
| 14 | Importación de archivos reales de Oficina/Material | los formatos reales suelen tener sorpresas que ningún CSV de ejemplo reproduce |
| 15 | Pruebas multiusuario con perfiles reales | varias personas a la vez, cada una desde su área |
| 16 | Backup integral + restore integral **después** de operar alpha.4 | restaurar a base temporal y arrancar contra ella |
| 17 | Revisión visual del usuario | la interfaz se rehízo por completo; hace falta que quien la usa a diario la vea antes de darla por buena |
| 18 | Estabilidad prolongada | días de operación continua, reinicios y concurrencia física |

## Criterio para dejar de llamarla alpha

Cerrar los puntos **10 a 18**. Los puntos 1 a 6 son limitaciones conocidas que no
impiden operar; los 7 a 9 son trabajo futuro planificado.

## Lo que esta entrega NO afirma

- No afirma que la interfaz sea la definitiva: se rehízo entera y necesita el
  juicio de quien la usa en campo.
- No afirma que los formatos reales de la oficina importen sin ajustes.
- No afirma haber probado el NAS real, ni concurrencia física, ni un ciclo
  completo de respaldo y restauración sobre datos de producción.
- No declara éxito por compilar ni por tener los gates en verde.


## Fase 1 Nube Local / sincronización — pendientes actuales

Los gates automáticos ya incluyen tres procesos Syncthing reales y simulación de
24 clientes lógicos. **No equivalen a PCs físicas de oficina.**

Pendiente antes de lectores/LLM:

- Companion Windows: discovery de Server Oficina, login por estación, journal
  offline, lease OPEN/CLOSE y cola idempotente.
- Gate físico 1 PC Windows + Latitude usando carpeta LAB.
- Gate físico posterior con 2 y 5 PCs.
- Cambio real de Wi-Fi/DHCP sin reconfigurar identidades.
- Operación con Internet desconectado.
- Edición concurrente real de XLSX/DOCX y recuperación de conflicto.
- Restore desde ContentStore histórico.
- Adapter NAS/Synology con staging, carga reanudable, hash y promoción atómica.
- Prueba de indisponibilidad NAS durante transferencia/hidratación.
- Definir y probar presupuesto de caché/eviction con réplicas mínimas verificadas.
- CFAPI/placeholder es diseño futuro; no está implementado.
- Separación completa `Core + Domain Pack` todavía no está terminada: existen
  módulos sísmicos explícitos en el repositorio.

### Hallazgos del relevo 2026-09-27 (ver `reports/RELEVO_FASE1_20260927.md`)

Corregidos en la rama candidata (con prueba automatizada):

- el observador Nube Local no arrancaba como proceso independiente
  (`NoReferencedTableError: projects`) — nunca había corrido fuera de pytest;
- un archivo restaurado con el mismo mtime/tamaño quedaba tombstoned para siempre;
- raíz de share ausente/desmontada registraba borrado masivo;
- un archivo problemático (colisión de mayúsculas, symlink, desaparece durante
  el hash) detenía el observador completo en bucle de reinicios;
- SHA-256 recalculado cada 5 s para archivos tocados sin cambio de contenido;
- `server-oficina-local-cloud.service` no se instalaba, sus `ReadWritePaths`
  no existían y el env no fijaba `SYNC_ROOT`/`VERSIONS_ROOT`;
- la release se nombraba sólo por VERSION: reinstalar la misma VERSION
  sobrescribía en caliente el código activo y anulaba el rollback;
- `MANIFEST.sha256` obsoleto: `VALIDAR_SERVER_OFICINA.sh` no llegaba a
  `PACKAGE_OK` con CI verde.

Abiertos:

- **UFW por subred**: 8080/Syncthing sólo desde la subred vigente; si el router
  nuevo usa otra subred el gate de cambio de Wi-Fi falla. Requiere decisión
  (p. ej. RFC1918 en la interfaz LAN) antes del gate 24.
- **Atribución de dispositivo** en el hub: sin Companion, `source_peer_id`
  queda vacío; Syncthing conoce `modifiedBy` pero no se consulta aún.
- **Rename** se registra como tombstone + documento nuevo (mismo SHA), sin
  vínculo explícito de renombrado.
- **Cuarentenas** (colisión, symlink, nombre no portable) sólo se registran en
  el journal; falta exponerlas como revisión humana en la UI.
- **Backup**: `backup.sh` no incluye `versions/` (ContentStore) ni la identidad
  Syncthing del hub.
- Syncthing de Debian (hub) y de Windows (PC) pueden diferir de mayor versión;
  CI prueba sólo 2.1.5.

### Estado tras la integración 2026-09-27 (rama `claude/syncthing-phase1-integration-v0.2`)

Resueltos en código y probados en CI/laboratorio (**no** en la Latitude):

- UFW por subred fija → reconciliador por red confiable (`scripts/lan_firewall.py`);
  gate de cambio de Wi-Fi sigue pendiente de ejecución física.
- Atribución de **equipo** vía `modifiedBy` de Syncthing (requiere API key y PC
  registrada). Persona y sesión: siguen requiriendo Companion.
- Backup de `versions/` (inventario + réplica externa opcional fail-closed) e
  identidad Syncthing del hub; restore con verificación de historial.
- Nueva auditoría: carrera hash/tamaño, reemplazo con igual tamaño y mtime,
  nombres NFD, subárbol ilegible, EIO, raíz vacía/cambio de dispositivo,
  `.partial` huérfanos, `current` en bucle en primera instalación, código de
  release editable por el operador, backup pre-upgrade omitido, retención que
  borraba `pre-upgrade-*`, observador caído tras DETENER/INICIAR.

Endurecimiento final (mismo PR, 2026-09-27), probado en CI/laboratorio, **no** en la Latitude:

- Identidad de red del firewall: MAC del gateway + perfil NetworkManager + SSID
  (antes `wifi:<SSID>` / `wired:<iface>`: otra red con el mismo SSID o la misma
  `eth0` en otra LAN heredaba la confianza). Router reemplazado exige
  `trust-current`.
- Instalación fail-closed: la API ya no pasa a `0.0.0.0` sólo por ver UFW
  activo ni se ignora un fallo del reconciliador (`|| true`); sin publicación
  demostrada queda en `127.0.0.1` y la instalación sale con 10.
- Restore: el dump se restaura en una base nueva en una sola transacción y se
  intercambia de forma atómica; antes `pg_restore --clean` sobre la base viva
  dejaba una restauración parcial con un dump truncado.

Siguen abiertos:

- Todos los gates físicos del runbook 52 (PRE, instalación, systemd, PostgreSQL,
  permisos, Syncthing hub, backup/restore, UFW, Wi-Fi, reinicios, POST, 1 PC).
- Rename/move sin vínculo explícito entre documentos.
- Pantalla de revisión humana para incidencias y conflictos.
- Retención/GC de `versions/` y configuración de la réplica externa real.
- Syncthing del hub (Debian) vs PCs (Windows): versión mayor por confirmar.
- Archivos muy grandes: tres lecturas al archivar y ciclo bloqueado mientras tanto.
- Companion Windows (persona, sesión, journal offline, leases reales).

### Administración GitHub pendiente

La integración GitHub usada por este trabajo no expone una mutación de
administración para eliminar colaboradores del repositorio. Los PR abiertos no
tienen revisores solicitados y no se encontró un ruleset que otorgue acceso,
pero **la revocación de un colaborador debe ejecutarse con credenciales de
administrador desde Settings → Collaborators**. Este pendiente no debe marcarse
como resuelto por un agente sin evidencia de esa operación.
