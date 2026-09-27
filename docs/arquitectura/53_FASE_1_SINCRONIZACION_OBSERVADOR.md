# 53 · Fase 1 — Sincronización PCs ↔ Latitude: arquitectura final, observador y gates

Fecha: 2026-09-27. Estado: **candidata de laboratorio**. Nada de este documento
declara producción: los gates físicos de §10 siguen pendientes.

## 1 · Arquitectura

```text
PC Windows ──Syncthing──┐                         ┌── systemd: server-oficina (API :8080)
PC Windows ──Syncthing──┼── Latitude (hub) ───────┼── systemd: server-oficina-local-cloud (observador)
                        │   /srv/server-oficina/  ├── systemd: syncthing@serveroficina-sync (LAB)
                        │     files/<share>/      ├── docker: server-oficina-postgres
                        │     versions/sha256/..  └── systemd: server-oficina-backup.timer
                        │                             systemd: server-oficina-lan-firewall.timer
```

Un namespace físico, un propietario de transporte: `files/` lo escribe sólo
Syncthing del hub; `versions/` sólo el observador; PostgreSQL sólo la API y el
observador.

## 2 · Responsabilidades

| Componente | Hace | No hace |
|---|---|---|
| **Syncthing** | transporta bloques PC ↔ hub, detecta cambios, conserva conflictos `.sync-conflict-*`, versionado Staggered de cambios remotos, `modifiedBy` por versión, marcador `.stfolder` | no sabe qué persona editó; no es historial propio del hub; no es backup |
| **Server Oficina (API)** | identidad de equipos y sesiones, leases, catálogo de shares, consulta de documentos/versiones, visibilidad del estado del observador | no escribe en `files/` ni en `versions/` (sólo lectura por systemd) |
| **Observador local-cloud** | recorre shares, ingiere archivos estables, archiva bytes en el ContentStore, registra versiones/tombstones/recuperaciones/conflictos, aísla incidencias, atribuye dispositivo | nunca modifica ni borra archivos de trabajo (`files/` es de sólo lectura para él por DAC y por `ProtectSystem=strict`); nunca purga historia |
| **ContentStore (`versions/`)** | objetos inmutables `sha256/xx/<hash>`, escritura `.partial` → fsync → verificación → promoción atómica | no es réplica externa: comparte disco con la base |

## 3 · Estados de un documento (`DocumentVersion.change_kind`)

| Estado | Cuándo | Contenido |
|---|---|---|
| `MODIFIED` | archivo nuevo o con contenido distinto, observado estable | SHA-256 del contenido archivado |
| `DELETED` | un archivo registrado desaparece **y la raíz del share es confiable** | tombstone: copia SHA/tamaño previos; los bytes siguen en `versions/` |
| `RECOVERED` | reaparece tras un `DELETED` con el **mismo SHA** (Papelera de Windows, `.stversions`) | el documento vuelve a estar vivo |
| `CONFLICT` | copia `.sync-conflict-*` de Syncthing | `analysis_status=CONFLICT_REVIEW`; nunca se fusiona a ciegas |

Si tras un `DELETED` aparece otro contenido en la misma ruta, es `MODIFIED`.
Un rename/move se registra como `DELETED` del origen + documento nuevo con el
mismo SHA (sin vínculo explícito todavía, ver §9).

## 4 · `DELETED` frente a recurso no disponible

El observador sólo registra borrados cuando puede demostrar que está viendo la
carpeta real. En caso contrario el share queda **UNAVAILABLE** y no se registra
ningún borrado:

| Código | Causa |
|---|---|
| `ROOT_MISSING` | la raíz no existe (disco/volumen ausente) |
| `ROOT_PERMISSION` | permiso denegado sobre la raíz |
| `ROOT_IO_ERROR` | error de E/S al abrir o recorrer (disco dañado) |
| `ROOT_NOT_DIRECTORY` / `ROOT_INACCESSIBLE` | la raíz no es un directorio / otro error |
| `SYNCTHING_MARKER_MISSING` | share Syncthing sin `.stfolder` (montaje vacío) |
| `ROOT_DEVICE_CHANGED` | la raíz cambió de dispositivo (montaje sustituido); requiere verificar y reiniciar el observador |
| `ROOT_EMPTY_UNVERIFIED` | share sin marcador, vacío, con documentos vivos |
| `OUTSIDE_SYNC_ROOT` | `local_root` fuera de `SERVER_OFICINA_SYNC_ROOT` |

Además, un **subdirectorio ilegible** protege todo su subárbol, y un archivo
problemático protege su propio documento. Syncthing aplica la misma regla: sin
`.stfolder` detiene la carpeta y no propaga borrados (verificado en laboratorio).

## 5 · Incidencias por archivo (aisladas, nunca detienen el ciclo)

`NAME_NOT_PORTABLE`, `CASE_COLLISION` (ninguna ruta gana), `SYMLINK`,
`STAT_FAILED`, `SUBTREE_UNREADABLE`, `CHANGED_DURING_INGEST`,
`INGEST_DEFERRED`, `STORE_LOW_SPACE`. Se registran una vez en el journal
(`LOCAL_CLOUD_SKIP share=... code=... path=...`) y se exponen en
`GET /api/local-cloud/shares` → `metadata.observer` (estado, código, hasta 50
incidencias). Errores sistémicos del disco en la ingesta (`ENOSPC`, `EROFS`,
`EIO` del ContentStore) sí terminan el proceso para que systemd lo haga visible.

## 6 · Integridad del hash y cuándo se recalcula

* Estabilidad: dos observaciones consecutivas con la misma huella
  `(tamaño, mtime_ns, inodo, ctime_ns)`.
* **Se reutiliza** el SHA-256 sin leer el archivo sólo si la huella es idéntica a
  la guardada en la última versión (`metadata.fingerprint`) o a la ya procesada
  por este proceso.
* **Se recalcula** ante cualquier diferencia: un reemplazo con igual tamaño y
  mtime cambia inodo/ctime; tras un reinicio del observador o una restauración
  del filesystem también.
* Tras archivar, la huella se vuelve a leer: si cambió, no se registra nada
  (`CHANGED_DURING_INGEST`) y se reintenta. El tamaño registrado es el del objeto
  archivado. `python -m app.workers.verify_history --deep` recalcula todo.
* Estados intermedios de cambios rápidos no se versionan (nunca fueron estables);
  Syncthing conserva en `.stversions` lo reemplazado remotamente.

## 7 · Versionado, espacio y recuperación

* `versions/` crece con cada contenido distinto (deduplicado por SHA). No hay
  retención automática: purgar exige política y réplicas verificadas.
* Reserva: `SERVER_OFICINA_VERSIONS_MIN_FREE_PERCENT` (10 % por defecto) del
  volumen de `versions/` nunca se ocupa, porque lo comparte PostgreSQL. Sin
  espacio el archivado se pausa (`LOCAL_CLOUD_STORE_LOW_SPACE`) y se reanuda solo.
* Al arrancar, el observador borra temporales `.partial-*` de copias
  interrumpidas (único escritor de `versions/`).
* Reinicio del observador, de Syncthing o del hub: el primer recorrido vuelve a
  esperar estabilidad; la huella evita recalcular lo ya registrado.

## 8 · Atribución: qué garantizamos en esta fase

| Dato | Estado | Fuente |
|---|---|---|
| share, ruta, SHA-256, tamaño, mtime, momento observado | **garantizado** | observador |
| **equipo** que introdujo la versión | **garantizado si** hay API key de Syncthing y el equipo está registrado como `SyncPeer` con su Device ID; `attribution.verified=true` sólo si Syncthing describe exactamente el archivo observado | `modifiedBy` de Syncthing (`metadata.attribution`, `source_peer_id`) |
| equipo en copias de conflicto | ID corto en el nombre `.sync-conflict-...-<ID>` | Syncthing |
| **persona** y **sesión** | **NO disponible**: `attribution.person = null` | requiere Companion Windows (login de estación, journal local) |
| cambios offline creados y borrados antes de llegar al hub | **NO recuperables** | requiere journal del Companion |

La atribución nunca bloquea la ingesta: con la API caída la versión se registra
con `method=none` y la causa.

## 9 · Permisos, servicios, instalación y rollback

| Ruta | Dueño / modo | Escribe |
|---|---|---|
| `/opt/server-oficina/releases/<id>` | `root`, sin escritura de grupo/otros | sólo el instalador |
| `/srv/server-oficina/files` | `root:serveroficina 2750` | Syncthing del hub (`serveroficina-sync`, grupo `serveroficina`) en su share |
| `/srv/server-oficina/versions` | `serveroficina 2750` | sólo el observador (`ReadWritePaths` único) |
| `/etc/server-oficina/server-oficina.env` | `root:serveroficina 0640` | instalador (conserva claves del operador) |

* Release: `VERSION+fecha.gCOMMIT[.dirty]`; nunca se reutiliza ni se sobrescribe
  un directorio; `current` cambia de forma atómica; la previa queda intacta.
* Instalación: validación del paquete dentro de la release → PostgreSQL sano →
  backup pre-upgrade obligatorio → promoción → health por sondeo → observador
  con 0 reinicios. Fallo de health: salida 5 y rollback. Fallo del observador:
  salida 7 y rollback, restaurando el estado previo del observador. Colisión:
  salida 6 sin tocar nada. Permisos incompatibles: salida 8.
* El rollback revierte el código; la base conserva las tablas nuevas (sólo
  aditivas). Para volver la base atrás se usa el dump `pre-upgrade-*`.
* `server-oficina-local-cloud` arranca con `server-oficina` (`WantedBy`) y se
  detiene con él (`Requires`).
* Firewall: `server-oficina-lan-firewall` confía por **identidad de red** —
  MAC del gateway (obligatoria) + UUID del perfil NetworkManager + SSID + medio,
  nunca sólo SSID ni nombre de interfaz—, deriva la subred en cada cambio y sólo
  abre puertos a la subred RFC1918 actual de la interfaz por defecto. Mismo
  SSID u otra LAN en la misma `eth0` → sin reglas; router reemplazado → exige
  `trust-current`. Identidad ilegible un momento: reglas mantenidas ≤ 600 s si
  interfaz/subred/gateway no cambian (ver `scripts/lan_firewall.py`).
* Publicación LAN fail-closed: la API escucha en `127.0.0.1` salvo que
  `configurar-acceso-lan.sh` demuestre UFW activo con entrada `deny`/`reject`,
  red confiable, reglas verificadas y health; si no, salida 10
  (`INSTALACION_SOLO_LOCAL`), nunca instalación "sana" expuesta.
* Restore: validación completa del respaldo (SHA, lectura entera del dump y del
  tar) → `pg_restore --single-transaction` en una base nueva → intercambio de
  nombres en un único COMMIT (la base previa queda como
  `server_oficina_pre_restore_<fecha>`) → health; si falla, vuelta atrás. Nunca
  una base parcial anunciada como restaurada (doc 36).

## 10 · Gates

| Gate | Dónde | Evidencia |
|---|---|---|
| Unitarios, contrato, observador, firewall, atribución | CI Python 3.12 y 3.13 | `pytest` |
| Paquete (`PACKAGE_OK`, MANIFEST estricto) | CI + copia limpia | `VALIDAR_SERVER_OFICINA.sh` |
| Syncthing real (transporte, 3 nodos) | CI | `syncthing_smoke.py` |
| Syncthing real + observador (19 escenarios) | CI + laboratorio local | `hub_worker_lab.py` |
| Instalador real en namespace aislado (16 escenarios, incl. publicación LAN fail-closed) | CI + laboratorio local | `installer_lab.py` |
| Restore real contra PostgreSQL efímero (9 escenarios) | CI + laboratorio local | `restore_lab.py` |
| **Latitude real**: PRE, instalación, systemd, PostgreSQL, permisos, Syncthing hub, backup/restore, UFW, cambio de Wi-Fi, reinicios, POST, 1 PC ↔ Latitude | **pendiente** | runbook 52 |

Laboratorio verde ≠ hardware validado. No se pasa a 2 PCs sin cerrar 1 PC ↔ Latitude.

## 11 · Riesgos conocidos

* Rename/move sin vínculo explícito entre documentos.
* Incidencias en metadatos del share y journal; falta pantalla de revisión.
* `versions/` sin retención; sin réplica externa configurada depende de un disco.
* Syncthing de Debian (hub) puede ser 1.x y el de Windows 2.x; CI prueba 2.1.5.
* Archivos muy grandes se leen tres veces al archivar (hash, copia, verificación)
  y bloquean el ciclo mientras tanto.
* `ROOT_DEVICE_CHANGED` exige reiniciar el observador tras verificar el montaje.
* El firewall necesita leer la MAC del gateway (ARP) y, en Wi-Fi, el SSID; sin
  ellos no hay reglas nuevas. Reemplazar el router exige `trust-current`.
* Una vez publicada la API, la protección de 8080 es UFW: un `ufw disable`
  manual la deja accesible hasta volver a ejecutar `configurar-acceso-lan.sh`.
* El restore necesita espacio para una segunda copia de la base mientras
  prepara; la base previa se conserva y se borra a mano tras verificar.
