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
| Código validado | `1e6af35eafc49f40215c7e4886541bb72e11653d` (este reporte se añade encima) |
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
