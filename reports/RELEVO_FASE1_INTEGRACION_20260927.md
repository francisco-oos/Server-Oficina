# Relevo Fase 1 · Integración Syncthing / observador local-cloud — 2026-09-27

Reporte factual de la candidata de integración. **No declara producción**: la
Latitude `server-oficina` no fue accesible desde el entorno de trabajo y ningún
gate físico se ejecutó.

## 1 · Repositorio y refs

| | Valor |
|---|---|
| Repositorio | `francisco-oos/Server-Oficina` |
| Rama base | `agent/openai/sync-core-v0.2` @ `ee5a8efdce993a91196eebcd50888567aa438e9f` |
| Rama anterior de Claude (conservada, sin reescribir) | `claude/wonderful-goldberg-dzyoeb` @ `e701cf590598794705c2a6e935f22b2d42d3ed02` |
| Rama candidata nueva | `claude/syncthing-phase1-integration-v0.2` |
| Código validado | `1e6af35eafc49f40215c7e4886541bb72e11653d` (relevo 2); `dc73634c14620f9e6113631671a9202633102c4b` tras el endurecimiento final (§14) |
| `main` | `2d40e558…` sin cambios; no contiene commits de Claude |
| PR draft | #3 → `agent/openai/sync-core-v0.2` (no fusionado) |

Baseline verificado al empezar: la rama de Claude estaba 6 por delante y 0 por
detrás de la base; la base no se había movido; PR #1 y PR #2 seguían en draft.

## 2 · Commits

Incorporados con `cherry-pick -x` (el árbol resultante fue idéntico al de
`e701cf5` antes de cualquier cambio nuevo):

| Nuevo | Origen | Asunto |
|---|---|---|
| `da02e3b` | `c59edba` | observador robusto frente a gate físico |
| `7efa3ea` | `e0a867c` | instalar observador y no sobrescribir la release activa |
| `af99bce` | `c323b0b` | contrato de paquete y laboratorio Syncthing + observador |
| `c4b45b2` | `42dd3f1` | runbook gate 1, pendientes, MANIFEST |
| `9568dfc` | `970e046` | reinicios del observador como delta |
| `b132c55` | `e701cf5` | reporte del relevo anterior (histórico, se conserva) |

Nuevos:

| Commit | Asunto |
|---|---|
| `7736a03` | auditoría del observador: carreras, Unicode, raíces no confiables |
| `8af26e8` | instalador: symlink `current` en bucle, código editable, backup omitido |
| `b6d1902` | UFW portable por red confiable, backup de historial e identidad del hub |
| `3bf83ee` | laboratorio Syncthing real ampliado; atribución tolera archivo no indexado |
| `6a285ff` | CI: gates en ramas de integración y laboratorio del instalador |
| `0a1a336` | MANIFEST |
| `025d8fc` | documentación final, CHANGELOG, runbook |
| `1e6af35` | MANIFEST |

Diff contra la base: 49 archivos (21 nuevos, 28 modificados), sin artefactos
(`.db`, `.pyc`, logs, claves) ni secretos. Las únicas IPs en código son los
bloques RFC1918 del reconciliador de firewall.

## 3 · Auditoría de lo heredado (los seis commits)

| Tema | Veredicto |
|---|---|
| MANIFEST / `PACKAGE_OK` | causa confirmada (manifiesto obsoleto desde `main`: 37 faltantes, 96 distintos). Corrección válida; se mantiene `--check` estricto en `VALIDAR`, en el instalador y en CI |
| `NoReferencedTableError` | causa real: el proceso del worker sólo importaba `local_cloud_models`, cuya FK `document_records.project_id → projects` requiere `app.db.models`. El import en el módulo de modelos es la corrección arquitectónica (la metadata queda completa para cualquier consumidor), no un parche en el worker. Test: worker como proceso aislado |
| Restauración (`RECOVERED`) | correcta; refinada: `RECOVERED` sólo con el mismo SHA |
| Raíz no disponible | incompleta: cubría raíz ausente y `.stfolder`, pero no subárbol ilegible, EIO, raíz vacía sin marcador ni montaje sustituido (corregido, §4) |
| Aislamiento por archivo | correcto, pero una excepción inesperada en un share seguía deteniendo a los demás (corregido) |
| Optimización de hash | reutilizaba el SHA con `(tamaño, mtime)`: un reemplazo con igual tamaño y mtime pasaba inadvertido (heredado de la base; corregido con inodo y ctime) |
| Instalador | correcto en lo principal; se hallaron cuatro defectos nuevos (§4) |
| Releases únicas | correcto |
| Permisos del observador | `ProtectSystem=strict` correcto, pero la app tenía escritura DAC sobre `files/`; ahora `root:serveroficina 2750` |

## 4 · Defectos encontrados y corregidos en esta ronda

Todos se reprodujeron antes de corregirlos (test que fallaba o laboratorio).

| # | Defecto | Reproducción |
|---|---|---|
| 1 | Carrera: archivo reescrito entre la observación y el hash → versión con tamaño 5 para un contenido de 52 bytes | test (`rewritten_between_snapshot_and_hash`) |
| 2 | Reemplazo con igual tamaño y mtime no detectado | test |
| 3 | Nombre NFD en disco nunca ingerido | test |
| 4 | Nombre con espacio inicial nunca ingerido | test |
| 5 | Subdirectorio ilegible → `DELETED` de todo su contenido | test (2 falsos borrados) |
| 6 | `EIO` al recorrer → caída del worker completo | test |
| 7 | Raíz vacía sin marcador con documentos vivos → borrado masivo | test |
| 8 | Raíz montada sobre otro dispositivo sin detectar | test |
| 9 | `.partial-*` huérfanos tras SIGKILL nunca se limpiaban | test |
| 10 | Primera instalación: `current -> current` (bucle) si el health fallaba (también en la base) | laboratorio del instalador |
| 11 | Código de la release con el dueño del checkout (uid 1000), editable sin sudo (también en la base) | reproducción con `rsync -a` |
| 12 | Backup pre-upgrade omitido en silencio si PostgreSQL existía pero no respondía | lectura + reorden verificado en laboratorio |
| 13 | `SHA256SUMS` del pre-upgrade con rutas absolutas | laboratorio (no verificable fuera del host) |
| 14 | Retención borraba `pre-upgrade-*`; `tar || true` ocultaba fallos | lectura del script |
| 15 | Dos respaldos en el mismo segundo compartían directorio | CI (el laboratorio lo detectó) |
| 16 | `DETENER` + `INICIAR` dejaba el observador caído (`Requires=` propaga stop, no start) | análisis de dependencias systemd |
| 17 | Firewall: `ipaddress.is_private` acepta 203.0.113.0/24; SSID vacío leía la línea siguiente | test del reconciliador |
| 18 | Atribución: un 404 de Syncthing desactivaba la atribución del ciclo | test |

## 5 · Mejoras adicionales

* Códigos de causa por raíz e incidencia; estado del observador en
  `GET /api/local-cloud/shares` → `metadata.observer`.
* Reserva de espacio en `versions/` (`SERVER_OFICINA_VERSIONS_MIN_FREE_PERCENT`,
  10 % por defecto) porque comparte volumen con PostgreSQL.
* `python -m app.workers.verify_history [--deep]` y `scripts/verificar-historial.sh`.
* Atribución técnica de **equipo** por `modifiedBy` de Syncthing (sólo con API
  key y PC registrada; `person: null`).
* Health por sondeo, `current` atómico, API con `files/` y `versions/` de sólo lectura.
* Reconciliador UFW por red confiable; backup con inventario, identidad del hub y
  réplica externa fail-closed; restore con verificación del historial.
* `evidencia-latitude.sh` amplía la evidencia PRE/POST (firewall, releases, `BACKUP_INFO`).

## 6 · Pruebas ejecutadas (estado final, copia limpia de `1e6af35`)

| Suite | Resultado exacto |
|---|---|
| pytest Python 3.12 | 192 passed, 1 warning (Starlette/AnyIO deprecado) |
| pytest Python 3.13 | 192 passed, 1 warning |
| Tests recolectados | 192 (base: 123) |
| `syntax-check.py` | `SYNTAX_OK (92 archivos)` |
| `VALIDAR_SERVER_OFICINA.sh` | `BACKEND_OK`, `FRONTEND_OK`, `DEPLOY_OK`, `MANIFEST_CHECK_OK 246 archivos`, **`PACKAGE_OK`**, exit 0 |
| shellcheck `-S warning` | 42 scripts + dispatcher, sin avisos |
| `systemd-analyze verify` | 6 unidades sin directivas inválidas (sólo falta el ejecutable fuera de la Latitude) |
| Laboratorio Syncthing real + observador (Syncthing v2.1.5) | `HUB_WORKER_LAB_OK`, 19/19 escenarios, Python 3.12 y 3.13 |
| Laboratorio del instalador real (namespace aislado) | `INSTALLER_LAB_OK`, 11/11 escenarios |
| Linters/type checkers configurados en el repo | no hay (sin mypy/ruff/flake8 configurados); se usó pyflakes ad hoc en archivos tocados |

Test que falla ejecutado **aislado**, preexistente en la base e idéntico ahora:
`tests/test_workstation_identity.py` (credenciales del admin dependen del orden de
la suite). En la suite completa pasa. No se relajó ningún test.

## 7 · CI de GitHub

Causa del CI principal no disparado antes: `local-cloud-ci.yml` sólo cubría
`push` a `agent/**`, y `pull_request` requiere un PR abierto. Ahora `agent/**` y
`claude/**` disparan los tres workflows, que también admiten `workflow_dispatch`.
No usan `pull_request_target`, `workflow_run` ni secretos, y el token es de sólo
lectura (`tests/test_ci_workflows.py`).

| Workflow | Commit | Run | Resultado |
|---|---|---|---|
| Server Oficina CI (3.12 + 3.13 + contrato de paquete) | `0a1a336` | 36285995391 | PASS |
| Syncthing Integration (3 contenedores + observador 19 escenarios) | `0a1a336` | 36285995375 | PASS |
| Installer Lab | `0a1a336` | 36285995412 | FAIL: harness del lab (tomaba el backup por orden alfabético); corregido en `025d8fc` |
| Server Oficina CI | `1e6af35` | 36286798668 (push), 36286819373 (PR) | PASS / PASS |
| Syncthing Integration | `1e6af35` | 36286798634 (push), 36286819457 (PR) | PASS / PASS |
| Installer Lab | `1e6af35` | 36286798620 (push), 36286819384 (PR) | PASS / PASS |

## 8 · Laboratorio Syncthing (Python 3.13, estado final)

Crear (hub en 2,0 s, registro en 3,5 s), modificar, renombrar, mover, borrar
(los bytes siguen en el ContentStore y en `.stversions`), restaurar con el mismo
mtime (`RECOVERED`), restore desde el historial (llega a pc1 en 1,5 s), hub
apagado con cambio pendiente (2,0 s), reinicio de pc1, reinicio del observador
(1,5 s), corte y recuperación de red (2,5 s).

También: conflicto offline (ambas versiones, `CONFLICT_REVIEW`), colisión de
mayúsculas en cuarentena y atribución de equipo verificada (PC1/PC2, persona
nula). Con 20 cambios rápidos se registró 1 versión, con tamaño coherente con el
objeto. El nombre no portable quedó aislado como `NAME_NOT_PORTABLE`. La caída
de la raíz del hub, simulada con un punto de montaje vacío, dio `UNAVAILABLE`
(`SYNCTHING_MARKER_MISSING`) con **0 borrados** en Server Oficina y ninguno
propagado por Syncthing; la recuperación terminó con 0 borrados y sin pérdidas
en pc1. `verify_history --deep`: `HISTORY_OK`.

Recursos del observador en toda la corrida: ~56 MiB RSS, 0,7 s de CPU.

## 9 · Laboratorio del instalador

`scripts/install-tablet.sh` real, sin modificar, dentro de un namespace de
montaje. Stubs sólo para docker, systemctl, curl (health), apt, ufw, sleep y date.

| Escenario | Salida | Resultado |
|---|---|---|
| primera instalación con health roto | 5 | `current` válido (antes: bucle) |
| instalación limpia | 0 | código root sin escritura g/o; `files` 0:serveroficina 2750; `versions` serveroficina 2750; env con `SYNC_ROOT`/`VERSIONS_ROOT`; backup con SHA válido; observador activo |
| reinstalar la misma VERSION | 0 | directorio nuevo; previa intacta (hash del árbol); clave del operador conservada |
| colisión forzada | 6 | `current` intacto |
| health falla | 5 | rollback; observador previo intacto |
| observador en bucle | 7 | rollback; observador previo sigue habilitado |
| rollback a release legado sin observador | 7 | `current` = legado; observador deshabilitado |
| backup sin réplica externa | 0 | inventario, identidad del hub 0600, aviso explícito |
| réplica externa no montada | 3 | fail-closed |
| réplica externa en tmpfs | 0 | `OK:2_nuevos`, objetos verificados |
| restore | 0 | observador detenido antes y rearrancado después; identidad no aplicada |

## 10 · Documentación actualizada

`docs/arquitectura/53_FASE_1_SINCRONIZACION_OBSERVADOR.md` (nuevo),
`docs/operacion/36_BACKUP_RESTORE.md`, `docs/operacion/52_RUNBOOK_GATE_1_PC_LATITUDE.md`,
`docs/operacion/07_INSTALACION_DEBIAN.md`, `docs/00_INDICE_DOCUMENTACION.md`,
`CHANGELOG.md`, `reports/PENDIENTES_REALES.md`, `.env.example`. El reporte del
relevo anterior se conserva sin cambios.

## 11 · Riesgos abiertos

* Rename/move sin vínculo explícito entre documentos.
* Falta una pantalla de revisión humana para incidencias y conflictos.
* `versions/` sin retención ni réplica externa configurada: depende de un disco.
* Versión mayor de Syncthing en Debian (hub) frente a Windows sin confirmar.
* Archivos muy grandes: tres lecturas al archivar y ciclo bloqueado mientras tanto.
* `ROOT_DEVICE_CHANGED` exige reiniciar el observador tras verificar el montaje.
* El reconciliador de firewall depende de identificar el SSID (`iw`); comportamiento
  con NetworkManager real pendiente de gate físico.
* Atribución de persona/sesión: requiere Companion.

## 12 · Gates

| Gate | Entorno | Resultado | Evidencia |
|---|---|---|---|
| Unitarios + contrato Python 3.12 | local | PASS | 192 passed |
| Unitarios + contrato Python 3.13 | local | PASS | 192 passed |
| Paquete `PACKAGE_OK` | local, copia limpia | PASS | log de `VALIDAR`, exit 0 |
| CI principal (3.12 + 3.13 + paquete) | GitHub | PASS | runs 36286798668, 36286819373 (`1e6af35`) |
| Syncthing real 3 nodos | GitHub | PASS | runs 36286798634, 36286819457 (`1e6af35`) |
| Syncthing real + observador | local 3.12/3.13 + GitHub | PASS | 19/19; mismos runs |
| Instalador real (namespace) | local + GitHub | PASS | 11/11; runs 36286798620, 36286819384 (`1e6af35`) |
| PRE real Latitude | hardware | NOT RUN | sin acceso |
| Instalación real / systemd / PostgreSQL | hardware | NOT RUN | — |
| Filesystem y permisos reales | hardware | NOT RUN | — |
| Syncthing con Latitude como hub | hardware | NOT RUN | — |
| Backup / restore reales | hardware | NOT RUN | — |
| UFW / cambio de Wi-Fi | hardware | NOT RUN | — |
| Reinicio / apagado-encendido | hardware | NOT RUN | — |
| POST | hardware | NOT RUN | — |
| 1 PC ↔ Latitude | hardware | NOT RUN | — |

## 13 · Siguiente paso

Revisión independiente del PR #3 y decisión de merge por el responsable. Después,
ejecutar `docs/operacion/52_RUNBOOK_GATE_1_PC_LATITUDE.md` en `server-oficina`.
**No pasar a 2 PCs** hasta cerrar el Gate 1 físico en verde.

## 14 · Endurecimiento final (relevo 3, mismo PR #3)

Última ronda antes del runbook 52. Misma rama y mismo PR; sin arquitectura
nueva. Los 18 defectos de §4 son la línea base y siguen cubiertos por la suite.

### 14.1 · Commits añadidos sobre `36a5ab8`

| Commit | Asunto |
|---|---|
| `b3c07e7` | firewall LAN: identidad de red por gateway y perfil, no por SSID/interfaz |
| `33d267a` | instalación fail-closed respecto a la publicación LAN |
| `2559997` | restore sin restauración parcial de la base viva |
| `c06e9ce` | documentación (07, 36, 52, 53, SECURITY, CHANGELOG, PENDIENTES) y MANIFEST |
| `dc73634` | restore valida el usuario de servicio antes de preparar (hallado por CI) |
| este commit | este reporte y MANIFEST |

### 14.2 · Identidad de red del firewall

Defecto: la confianza se guardaba como `wifi:<SSID>` o `wired:<iface>`. Con el
reconciliador de `36a5ab8`, un punto de acceso con el mismo SSID en otro router
y otra LAN enchufada a la misma `eth0` **recibían reglas 8080** (reproducido en
test antes de corregir).

Ahora (`scripts/lan_firewall.py`) la identidad es:

| Componente | Origen | Obligatorio |
|---|---|---|
| `gw_mac` | `ip -4 neigh show <gateway> dev <iface>` (con un ping para poblar ARP) | **sí** |
| `nm` | UUID del perfil activo (`nmcli -t -f DEVICE,UUID connection show --active`) | si NetworkManager gestiona la interfaz |
| `ssid` | `iw dev <iface> link` | en Wi-Fi |
| `medium` | `wifi` / `wired` | sí |

Una red es confiable sólo si **todos** los componentes guardados coinciden. La
subred no forma parte de la identidad: se deriva en cada ejecución.

* Nueva IP por DHCP, o el mismo router con otro rango: misma identidad; las
  reglas siguen solas a la subred nueva.
* Mismo SSID u otra LAN en la misma `eth0`: otro gateway → sin reglas.
* Router reemplazado: exige `trust-current` (compromiso asumido y documentado:
  portabilidad frente a seguridad; no se edita ninguna IP).
* Identidad ilegible un momento (ARP vacío, NetworkManager reiniciando o con
  error): se **mantienen** las reglas sólo si interfaz, subred y gateway no
  cambian y durante ≤ `SO_LAN_FIREWALL_HOLD_SECONDS` (600 s); luego se cierran.
  Si cambia la subred, se cierran de inmediato.
* Sin NetworkManager: la huella es gateway + medio (+ SSID en Wi-Fi); nunca
  SSID solo ni nombre de interfaz solo.
* Confianzas antiguas (`wifi:`/`wired:`) se ignoran; hay que confiar una vez.
* Se mantiene: sólo RFC1918 (lista explícita), sólo en la interfaz por
  defecto, nunca `allow from anywhere`, nunca se tocan reglas ajenas (SSH);
  la primera ejecución nunca confía implícitamente (`--trust-current-if-empty`
  eliminado).

### 14.3 · Qué pasa ahora si el firewall falla

Antes: `install-tablet.sh` fijaba `SERVER_OFICINA_HOST=0.0.0.0` con sólo ver
UFW activo y ejecutaba `configurar-acceso-lan.sh || true`: una instalación
«sana» podía quedar escuchando en la LAN sin reglas verificadas.

Ahora:

1. El instalador escribe siempre `SERVER_OFICINA_HOST=127.0.0.1`.
2. Si UFW está activo, `configurar-acceso-lan.sh` (sin `|| true`) sólo publica
   si demuestra: UFW activo con `Default: deny|reject (incoming)`, red
   confiable, `lan_firewall.py apply --require-rules` con reglas verificadas y
   `/api/health` tras escuchar en `0.0.0.0` → `LAN_PUBLICADA`.
3. Cualquier fallo, incluido un error inesperado (trap `EXIT`), deja la API en
   `127.0.0.1` (reiniciándola si hacía falta), imprime
   `LAN_NO_PUBLICADA: <causa>` y sale con 10. El instalador vuelve a forzar
   `127.0.0.1` por defensa en profundidad y termina con
   `INSTALACION_SOLO_LOCAL` y **salida 10**: nunca se declara sana una
   instalación que esperaba LAN y no la tiene.
4. El rollback restaura también el env previo.
5. Nunca desactiva UFW, nunca abre 8080 globalmente, nunca toca SSH.
6. `--confiar-red-actual` (instalador o script) es la decisión explícita.

Riesgo residual documentado: tras publicar, la protección de 8080 es UFW; un
`ufw disable` manual la expone hasta volver a ejecutar `configurar-acceso-lan.sh`.

### 14.4 · Garantías del restore

Defecto reproducido con PostgreSQL real: el restore de `36a5ab8` ejecutaba
`pg_restore --clean` sobre `server_oficina`. Con un dump truncado (SHA256SUMS
coherente) terminó con salida 1, `documents` y `lab_marker` **vacías**,
`projects` y una tabla de un esquema posterior (`newer_feature`) mezcladas, API
y observador **detenidos** y ningún mensaje de fallo explícito.

Ahora (`scripts/restore.sh`):

| Fase | Garantía | Salida si falla |
|---|---|---|
| Validación | SHA256SUMS estricto; dump leído entero (`pg_restore -f /dev/null`); `tar -tzf` entero y sólo `imports/`/`evidence/`; base y usuario de servicio existen | 20, nada tocado |
| Preparación | base nueva con `pg_restore --single-transaction --exit-on-error --no-owner`; staging de archivos | 21, staging descartado; base viva, archivos y servicios intactos (nunca detenidos) |
| Intercambio | un único COMMIT de dos `ALTER DATABASE … RENAME`; base previa conservada como `server_oficina_pre_restore_<fecha>`; `imports/`/`evidence/` previos **movidos** a `.pre-restore-<fecha>/` | vuelta atrás |
| Health | `RESTORE_OK` sólo tras `/api/health` con los datos restaurados | 22 revertido; 23 `RESTORE_FAIL_CRITICO` con servicios detenidos a propósito |

Archivos extra en `data/app` (subidos después del respaldo): no se borran;
quedan en `.pre-restore-<fecha>/` con `DIFERENCIAS_CON_RESPALDO.tsv`
(`ausente_en_respaldo` / `distinto_en_respaldo`). Sólo se eliminan la base
temporal y el staging creados por la propia ejecución, con nombre único.
Resultado de cada ejecución en `backups/restore-logs/restore-<fecha>.txt`.

Evaluado y descartado: `pg_restore --clean --single-transaction` sobre la base
viva. Es atómico ante un fallo, pero (a) `--clean` no puede eliminar objetos de
los que dependen objetos de un esquema posterior (en el laboratorio:
`cannot drop constraint projects_pkey … constraint newer_feature_project_id_fkey
depends on index projects_pkey`), así que restaurar un respaldo anterior a una
migración fallaría siempre; (b) una vez confirmado, si el health falla no hay
vuelta atrás (la base previa ya no existe); (c) obliga a detener los servicios
durante toda la restauración. Base nueva + intercambio de nombres evita las tres.

### 14.5 · Pruebas nuevas

| Prueba | Cubre |
|---|---|
| `tests/test_lan_firewall.py` (32 casos, reescrito) | los 7 pedidos: misma red + IP nueva; misma identidad + subred nueva; mismo SSID otra red; misma `eth0` otra red; red nueva no confiable; red pública; pérdida temporal de identidad. Además: perfil NM en otro router, otro perfil en el mismo router, primera ejecución, error de NM, Wi-Fi sin SSID, entradas antiguas, puertos opcionales, reglas antiguas y SSH, idempotencia, UFW inactivo, fallo al aplicar, RFC1918, parsers |
| `installer_lab.py` s2a–s2e | sin red confiable → salida 10, `127.0.0.1`, regla antigua retirada, SSH intacta; reconciliador que falla → salida 10, `127.0.0.1`, sin reglas; con confianza → `0.0.0.0` y regla sólo de la subred; política `allow` → despublica; misma `eth0` en otra LAN → despublica. s4: rollback restaura el env |
| `restore_lab.py` (9 escenarios, PostgreSQL real) | defecto con el script anterior; dump truncado (20); fallo a mitad de `pg_restore` (21); tar truncado y tar con `../` (20); SHA inválido (20); health falla → revierte todo (22); health falla siempre → 23 con servicios detenidos; restore correcto de esquema anterior con archivo extra conservado (0) |
| `test_deploy_contract.py` | `test_lan_publication_is_fail_closed`, `test_restore_never_leaves_a_partial_live_database` |

### 14.6 · Validación (código `dc73634`)

| Suite | Resultado exacto |
|---|---|
| pytest Python 3.12 | 206 passed, 1 warning (Starlette/AnyIO deprecado) |
| pytest Python 3.13 | 206 passed, 1 warning |
| `VALIDAR_SERVER_OFICINA.sh` (copia limpia `git archive`) | `SYNTAX_OK (93 archivos)`, `BACKEND_OK`, `FRONTEND_OK`, `DEPLOY_OK`, `MANIFEST_CHECK_OK 248 archivos`, **`PACKAGE_OK`**, exit 0 |
| shellcheck `-x -S warning` | 42 scripts + dispatcher NetworkManager, sin avisos |
| `systemd-analyze verify` | 6 unidades sin directivas inválidas (sólo falta el ejecutable fuera de la Latitude) |
| Syncthing real + observador (v2.1.5) | `HUB_WORKER_LAB_OK`, 19/19, Python 3.12 y 3.13 (local sobre `c06e9ce`; `dc73634` sólo toca restore; CI sobre `dc73634`) |
| Instalador real (namespace) | `INSTALLER_LAB_OK`, 16/16 |
| Restore real (PostgreSQL 16 efímero) | `RESTORE_LAB_OK`, 9/9; repetido también sin el usuario `serveroficina` en el host |

### 14.7 · CI de GitHub

| Workflow | Commit | Run | Resultado |
|---|---|---|---|
| Server Oficina CI | `c06e9ce` | 36290552739 (push), 36290554869 (PR) | PASS / PASS |
| Syncthing Integration | `c06e9ce` | 36290552701 (push), 36290554888 (PR) | PASS / PASS |
| Installer Lab | `c06e9ce` | 36290552745 (push), 36290554887 (PR) | FAIL: job `restore`; el runner no tiene el usuario `serveroficina` → `chown` falló en la preparación (salida 21, nada tocado, pero como «error inesperado»). Corregido en `dc73634` |
| Server Oficina CI | `dc73634` | 36296115932 (push), 36296119108 (PR) | PASS / PASS |
| Syncthing Integration | `dc73634` | 36296116050 (push), 36296119092 (PR) | PASS / PASS |
| Installer Lab (`installer` + `restore`) | `dc73634` | 36296115897 (push), 36296119117 (PR) | PASS / PASS |

El commit de este reporte sólo añade texto y MANIFEST; su CI se consigna en el PR.

### 14.8 · Gates tras el endurecimiento

| Gate | Entorno | Resultado |
|---|---|---|
| Unitarios + contrato 3.12 / 3.13 | local + GitHub | PASS (206) |
| Paquete `PACKAGE_OK` | local copia limpia + GitHub | PASS |
| Firewall: identidad de red (32 casos, incluidos los 7 pedidos) | local + GitHub | PASS |
| Publicación LAN fail-closed (reconciliador que falla) | laboratorio del instalador, local + GitHub | PASS |
| Restore transaccional (9 escenarios) | PostgreSQL efímero, local + GitHub | PASS |
| Syncthing real + observador | local + GitHub | PASS |
| PRE, instalación, systemd, PostgreSQL 18.6, permisos, hub, backup/restore, UFW y cambio de Wi-Fi con NetworkManager real, reinicios, POST, 1 PC ↔ Latitude | hardware (Latitude) | **NOT RUN** |

Laboratorio verde ≠ hardware validado. El siguiente paso sigue siendo §13: revisión
independiente y, después, el runbook 52 en `server-oficina`.

## 15 · Multi-interfaz / multi-LAN: Ethernet + Wi-Fi a la vez (mismo PR #3)

### 15.1 · Requisito aclarado y limitación que tenía `0f49c8e`

La Latitude tendrá Ethernet y Wi-Fi activas **simultáneamente**, cada una en una
LAN de la oficina, y debe poder encontrarse y usarse desde cualquiera de las dos.
En `0f49c8e`, `detect_network()` leía `ip route show default`, elegía **una**
interfaz y `desired_rules()` sólo generaba reglas para ella: con cable y Wi-Fi a
la vez sólo quedaba publicada la interfaz de la ruta por defecto. El alcance de
esta corrección se limita a firewall, descubrimiento local, runbook y pruebas;
observador, restore y ContentStore no se tocan.

### 15.2 · Commits

| Commit | Asunto |
|---|---|
| `b46477e` | firewall LAN multi-interfaz (Ethernet + Wi-Fi a la vez) |
| `0b46c01` | laboratorio multi-LAN con red real |
| `1128e05` | MANIFEST |
| `dbd9b32` | documentación (52, 07, 50, 53, SECURITY, CHANGELOG, PENDIENTES) y ajuste del laboratorio |
| este commit | este reporte y MANIFEST |

### 15.3 · Modelo

* `detect_networks() -> list[Network]`: todas las NIC físicas Ethernet/Wi-Fi
  (`/sys/class/net/<if>/device`; Wi-Fi si tiene `wireless`/`phy80211`), en estado
  `up`, no esclavas de un bridge y con IPv4 global. El nombre no importa (`enp…`,
  `wlp…`, `enx…`, `eth0`). Docker (`172.17.0.1/16`, RFC1918), veth, bridges y VPN
  quedan fuera (hay un test explícito).
* Por interfaz, de forma independiente: interfaz, dirección, subred, gateway (la
  ruta por defecto de esa interfaz, menor métrica), MAC del gateway, medio,
  SSID, perfil NetworkManager y estado (`confiable`, `hold`, `no_confiable`,
  `sin_identidad`, `no_rfc1918`).
* Confianza por LAN; el nombre de interfaz no forma parte de la identidad.
  `/etc/server-oficina/lan-firewall.json`:

```json
{"trusted_networks": [
  {"id": "medium=wired|gw_mac=aa:bb:cc:00:00:0a",
   "components": {"medium": "wired", "gw_mac": "aa:bb:cc:00:00:0a", "nm": "<uuid>"},
   "first_iface": "enp0s31f6", "first_subnet": "192.168.10.0/24"},
  {"id": "medium=wifi|ssid=Oficina|gw_mac=aa:bb:cc:00:00:0b",
   "components": {"medium": "wifi", "ssid": "Oficina", "gw_mac": "aa:bb:cc:00:00:0b", "nm": "<uuid>"},
   "first_iface": "wlp2s0", "first_subnet": "192.168.48.0/24"}],
 "syncthing": true, "mdns": true, "publish_api": true}
```

  El estado por interfaz (subred y gateway actuales, reglas, `hold_since`) vive en
  `/var/lib/server-oficina/lan-firewall-state.json`; el formato anterior se
  convierte solo.
* `trust-current --interface IF` (repetible) y `--confiar-interfaz IF` en el
  instalador y en `configurar-acceso-lan.sh`. Sin `--interface` sólo actúa si hay
  exactamente una LAN activa: una LAN nunca se confía por estar enchufada a la
  vez que otra.
* Reconciliación **incremental** con el formato real de `ufw status numbered`
  (verificado con UFW 0.36.2 en un namespace de red, incluido el nombre de
  interfaz de 15 caracteres): se borran sólo las reglas propias que sobran y se
  añaden las que faltan. Una LAN que cae o cambia sólo toca sus reglas.
* HOLD por interfaz.
* Un bloqueo compartido evita que el timer pise a
  `configurar-acceso-lan.sh` a mitad de una publicación. El dispatcher reacciona
  también a `down`/`reapply`.
* `apply --sync-api` (servicio systemd): con la intención de publicar registrada
  (`api on`, sólo tras una publicación demostrada), `0.0.0.0` mientras UFW esté
  activo con entrada `deny`/`reject` y quede al menos una LAN confiable con reglas
  verificadas; si no, `127.0.0.1`. La API sólo se reinicia en esa transición.
* `audit` (sólo lectura) comprueba:
  - Avahi: activo, sin reflector, sin interfaces excluidas, nombre `server-oficina.local`;
  - no-enrutamiento: `ip_forward`, política FORWARD, UFW `DEFAULT_FORWARD_POLICY`, NAT de una LAN;
  - escucha de Syncthing y de la API.

### 15.4 · Reglas UFW reales con Ethernet + Wi-Fi

Salida de `ufw status numbered` en el laboratorio (UFW real; en la Latitude
cambian los nombres de interfaz y las subredes):

```
[ 1] 22/tcp                     ALLOW IN    Anywhere                   # ssh
[ 2] 8080/tcp on enp0s31f6      ALLOW IN    192.168.10.0/24            # server-oficina-lan
[ 3] 8080/tcp on wlp2s0         ALLOW IN    192.168.48.0/24            # server-oficina-lan
[ 4] 21027/udp on enp0s31f6     ALLOW IN    192.168.10.0/24            # server-oficina-lan
[ 5] 22000/tcp on enp0s31f6     ALLOW IN    192.168.10.0/24            # server-oficina-lan
[ 6] 22000/udp on enp0s31f6     ALLOW IN    192.168.10.0/24            # server-oficina-lan
[ 7] 21027/udp on wlp2s0        ALLOW IN    192.168.48.0/24            # server-oficina-lan
[ 8] 22000/tcp on wlp2s0        ALLOW IN    192.168.48.0/24            # server-oficina-lan
[ 9] 22000/udp on wlp2s0        ALLOW IN    192.168.48.0/24            # server-oficina-lan
[10] 5353/udp on enp0s31f6      ALLOW IN    192.168.10.0/24            # server-oficina-lan
[11] 5353/udp on wlp2s0         ALLOW IN    192.168.48.0/24            # server-oficina-lan
```

### 15.5 · Cuando cae una interfaz (medido con red real)

* Cae la Wi-Fi: el reconciliador retira sólo las 5 reglas `on wlp2s0` (0 añadidas).
  Las de `enp0s31f6` no se tocan, la API conserva el mismo PID en `0.0.0.0`, el
  HTTP por cable sigue, la sesión Syncthing por cable es la misma (`startedAt`
  sin cambio) y un archivo nuevo se sincroniza por cable durante la caída.
* Vuelve la Wi-Fi: vuelven sus reglas sin nueva confianza, `server-oficina.local`
  vuelve a resolver en la LAN B y un archivo nuevo se sincroniza por Wi-Fi. Con
  un corte breve (~10 s) la sesión TCP de Syncthing sobrevivió: no se afirma
  "reconexión", sino que la LAN vuelve a sincronizar.
* Cae y vuelve el cable: simétrico.
* Cable en una LAN ajena (otro router): `enp0s31f6` queda `no_confiable` y sin
  reglas; la Wi-Fi sigue publicada; `trust-current` sin `--interface` se niega.
  Al volver el router original, la Ethernet se publica sin nueva confianza.
* Ninguna LAN: la API pasa a `127.0.0.1` (se reinicia y `ss` muestra
  `127.0.0.1:8080`). Al volver, pasa a `0.0.0.0`.

### 15.6 · `server-oficina.local` en cada LAN

Auditoría: no había configuración propia de Avahi. El paquete de Debian anuncia
el hostname en todas las interfaces sin reflector, y eso es lo que se quiere. No
se modifica Avahi; `audit` y el runbook lo verifican. Con Avahi 0.8 real en el
laboratorio:

```
Registering new address record for 192.168.48.109 on wlp2s0.IPv4.
Registering new address record for 192.168.10.23 on enp0s31f6.IPv4.
Server startup complete. Host name is server-oficina.local.
```

Una consulta mDNS desde la PC de la LAN A devuelve **sólo** `192.168.10.23`; desde
la de la LAN B, **sólo** `192.168.48.109`. No hay reflector ni reenvío.

Hallazgo que requiere decisión del responsable: UFW 0.36.2 trae en
`before.rules` `-A ufw-before-input -p udp -d 224.0.0.251 --dport 5353 -j ACCEPT`.
Lo verifiqué en el paquete de Ubuntu 24.04; en Debian 13 lo comprueba `audit`.
Por eso el mDNS multicast se acepta en cualquier interfaz, y en una LAN no
confiable directamente conectada la Latitude también responde a
`server-oficina.local` (medido: fase 0). 8080 y 22000 siguen cerrados allí. Las
reglas 5353 propias limitan el mDNS unicast (medido: bloqueado sin confianza,
permitido con ella). Evitar la respuesta en LAN ajenas exigiría restringir Avahi
por nombre de interfaz, lo que choca con la confianza por identidad de red. No
se implementó.

### 15.7 · Syncthing en ambas LAN

Escucha `default`: tcp y quic en `0.0.0.0:22000`/`[::]:22000`, y 21027/udp. Con
descubrimiento local, sin global, relays ni NAT:
- el hub conectó con la PC A por `192.168.10.50:22000` y con la PC B por `192.168.48.60:22000`;
- cada PC ve al hub en la IP de **su** LAN;
- un archivo de cada PC llegó al hub;
- caída de una interfaz: la sesión de la otra sigue (`startedAt` igual) y sincroniza.

### 15.8 · La Latitude no enruta

Ningún script habilita forwarding, bridge, NAT ni reflector (test de contrato).
En el laboratorio, con una ruta forzada desde la PC A hacia la LAN B vía la
Latitude, la conexión:
- **falla** con `ip_forward=0`;
- **falla** con `ip_forward=1` (como con Docker) y la política FORWARD DROP de UFW;
- **cruza** con FORWARD ACCEPT. Es el control positivo, que demuestra que la
  prueba detectaría enrutamiento.

### 15.9 · Pruebas añadidas

| Pedido | Test unitario (`tests/test_lan_firewall.py`, 60 casos) | Red real (`multi_lan_lab.py`) |
|---|---|---|
| 1 Ethernet sola | `test_ethernet_only_trusted` | — |
| 2 Wi-Fi sola | `test_wifi_only_trusted` | — |
| 3 ambas | `test_ethernet_and_wifi_trusted_simultaneously` | fase 1 |
| 4 cae Wi-Fi | `test_wifi_drops_ethernet_keeps_serving` | fase 2 |
| 5 cae Ethernet | `test_ethernet_drops_wifi_keeps_serving` | fase 4 |
| 6 regresa | `test_dropped_interface_returns_without_new_trust` | fases 3 y 5 |
| 7 Wi-Fi confiable + Ethernet desconocida | `test_trusted_wifi_and_unknown_ethernet` | fase 6 |
| 8 Ethernet confiable + Wi-Fi desconocida | `test_trusted_ethernet_and_unknown_wifi` | — |
| 9 subredes distintas | `test_two_trusted_lans_with_different_subnets` | fase 1 |
| 10 DHCP Ethernet | `test_independent_dhcp_change_on_ethernet` | — |
| 11 DHCP Wi-Fi | `test_independent_dhcp_change_on_wifi` | — |
| 12 router de una LAN | `test_router_change_in_one_lan_does_not_affect_the_other` | fase 6 |
| 13 reglas simultáneas | `test_ufw_keeps_simultaneous_rules_per_interface` | fase 1 (UFW real) |
| 14 Syncthing en ambas | `test_syncthing_ports_on_both_lans` | fases 1-5 (Syncthing real) |
| 15 mDNS limitado | `test_mdns_limited_to_trusted_interfaces` | fases 0-1 (Avahi real) |
| 16 ninguna LAN → loopback | `test_api_host_follows_trusted_lans`, `test_api_loopback_when_ufw_not_protecting` | fase 7 |

Además:
- **Tests unitarios:**
  - detección (sólo NIC físicas, cualquier nombre, esclava de bridge fuera);
  - confianza por red y no por nombre (adaptador USB);
  - perfiles NM por interfaz;
  - HOLD sólo de la interfaz afectada;
  - estado antiguo convertido;
  - reglas propias duplicadas o no reconocidas;
  - `status` de sólo lectura;
  - parser con salida real de UFW;
  - auditoría (Avahi, enrutamiento, escucha).
- **Laboratorio del instalador,** escenarios s2f–s2h (21 en total):
  - `--confiar-red-actual` con dos LAN se niega;
  - `--confiar-interfaz` ×2 publica ambas con una URL por LAN;
  - caída de la Wi-Fi sin reiniciar la API;
  - ninguna LAN → loopback;
  - vuelven ambas.
- **Test de contrato:** multi-interfaz, y la Latitude nunca enruta.

### 15.10 · Validación (código `dbd9b32`, copia limpia `git archive`)

| Suite | Resultado exacto |
|---|---|
| pytest Python 3.12 / 3.13 | 235 passed, 1 warning / 235 passed, 1 warning |
| `VALIDAR_SERVER_OFICINA.sh` | `SYNTAX_OK (94 archivos)`, `BACKEND_OK`, `FRONTEND_OK`, `DEPLOY_OK`, `MANIFEST_CHECK_OK 249 archivos`, **`PACKAGE_OK`** |
| shellcheck `-x -S warning` | sin avisos |
| `systemd-analyze verify` | sin directivas inválidas (sólo falta el ejecutable fuera de la Latitude) |
| Syncthing real + observador | `HUB_WORKER_LAB_OK` 19/19 en 3.12 y 3.13 |
| Instalador real (namespace) | `INSTALLER_LAB_OK` 21/21 |
| Restore real (PostgreSQL 16) | `RESTORE_LAB_OK` 9/9 |
| Red real multi-LAN (UFW, Avahi 0.8, Syncthing 2.1.5) | `MULTI_LAN_LAB_OK` 11/11 fases |

Incidencia local, no del código: una primera ejecución del laboratorio del
instalador falló en s5. Dentro de la release, un test del observador vio
`LOCAL_CLOUD_STORE_LOW_SPACE`: el contenedor quedó por debajo de la reserva del
10 % por los ~5 GB de laboratorios anteriores, y el observador pausó el
archivado como debe. Tras borrar esos directorios pasó 21/21. En CI no ocurrió.

### 15.11 · CI de GitHub

| Workflow | `1128e05` | `dbd9b32` |
|---|---|---|
| Server Oficina CI (3.12 + 3.13 + paquete) | 36300806812 / 36300809609 PASS | 36301285027 / 36301287365 PASS |
| Syncthing Integration | 36300806809 / 36300809599 PASS | 36301285002 / 36301287351 PASS |
| Installer Lab (`installer`, `restore`, `multi-lan`) | 36300806883 / 36300809611 PASS | 36301285037 / 36301287324 PASS |

En el runner de GitHub (kernel con IPv6), `multi-lan` pasó las 11 fases. Allí el
namespace nace con `ip_forward=1`; desde `dbd9b32` el laboratorio fija
`ip_forward=0` antes de medir, para que la etiqueta sea exacta en cualquier host.

### 15.12 · Gates

| Gate | Entorno | Resultado |
|---|---|---|
| Firewall multi-LAN (60 tests, 16 casos pedidos) | local + GitHub | PASS |
| Instalador con Ethernet + Wi-Fi (s2f–s2h) | local + GitHub | PASS |
| Red real multi-LAN: UFW por interfaz, `server-oficina.local` por LAN, Syncthing por ambas, caída/regreso, LAN ajena, ninguna LAN, no-enrutamiento | local + GitHub (namespaces; Wi-Fi simulada) | PASS |
| Latitude real: PC → Ethernet, PC → Wi-Fi, ambas a la vez, pérdida/recuperación de cada interfaz, `server-oficina.local` en cada LAN, SSH, Syncthing | hardware | **NOT RUN** |
| Resto de gates físicos (PRE, instalación, systemd, PostgreSQL 18.6, backup/restore, reinicios, POST, 1 PC ↔ Latitude) | hardware | **NOT RUN** |

Laboratorio verde ≠ hardware validado. Siguen sin probarse la radio Wi-Fi real,
NetworkManager real (perfiles, dispatcher), Avahi con el Wi-Fi de la oficina,
el aislamiento de clientes del punto de acceso y el resolvedor `.local` de
Windows. **No se pasa a 2 PCs** hasta cerrar el Gate 1 físico con el runbook 52
(§7 incluido).
