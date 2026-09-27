# Relevo Fase 1 · Sincronización PCs ↔ Latitude — 2026-09-27

Reporte factual. Nada aquí declara producción. **La Latitude no fue accesible
desde el entorno de este relevo** (contenedor cloud sin ruta a la LAN de la
oficina): no hay PRE/POST físicos ni gates físicos ejecutados.

## Base y HEAD

| | Commit |
|---|---|
| Base autoritativa | `ee5a8efdce993a91196eebcd50888567aa438e9f` (`agent/openai/sync-core-v0.2`, PR #2 draft) |
| CI base en GitHub | Server Oficina CI run 36273861079 ✅ · Syncthing Integration run 36273861072 ✅ |
| Rama de trabajo | `claude/wonderful-goldberg-dzyoeb` (creada desde la base; `main` y la rama del PR sin tocar) |
| Código validado | `42dd3f1` (suite, laboratorio, CI GitHub) + `970e046` (delta de reinicios del observador en el instalador) |

Commits: `c59edba` observador, `e0a867c` instalador/despliegue, `c323b0b` CI y
laboratorio, `42dd3f1` runbook/pendientes/MANIFEST, `970e046` ajuste del
instalador, más este reporte. `VALIDAR_SERVER_OFICINA.sh` se repitió en copia
limpia del commit final del reporte.

## Accesibilidad de la Latitude

```text
getent hosts server-oficina.local  -> sin resolución
192.168.48.109:22 / :8080          -> timeout
```

Se entrega `scripts/evidencia-latitude.sh PRE|POST` (sólo lectura, sin secretos)
y `docs/operacion/52_RUNBOOK_GATE_1_PC_LATITUDE.md`.

## Hallazgos (todos reproducidos antes de corregir)

| # | Hallazgo | Reproducción | Impacto en la Latitude |
|---|---|---|---|
| 1 | `VALIDAR_SERVER_OFICINA.sh` no llega a `PACKAGE_OK` con CI verde: `MANIFEST.sha256` obsoleto desde `main` (37 faltantes, 96 distintos) | copia limpia de la base → `EXIT=1` | `INSTALAR_EN_TABLETA.sh` abortaba en `verify-package.sh` dejando un directorio de release huérfano |
| 2 | El observador, lanzado como lo hace systemd, cae en el primer archivo: `NoReferencedTableError: ... 'projects'` | `python -m app.workers.local_cloud_worker --once` sobre la base | bucle de reinicios; ninguna versión registrada. Nunca había corrido fuera de pytest |
| 3 | Archivo borrado y restaurado con igual mtime/tamaño (Papelera de Windows, `.stversions`) queda tombstoned para siempre | test unitario y laboratorio con Syncthing real (timeout en la base) | gate delete/restore fallaría |
| 4 | `server-oficina-local-cloud.service` no se instalaba; sus `ReadWritePaths` (`files/`, `versions/`) no los creaba el instalador; el env no fijaba `SYNC_ROOT`/`VERSIONS_ROOT` (el ContentStore iba a `data/app/versions`) | test de contrato falla contra la base | la unidad no arranca con rutas inexistentes (comportamiento documentado de systemd; no reproducido aquí por falta de systemd PID 1) |
| 5 | Release nombrada sólo por VERSION: la rama base del PR ya usa `0.2.0-alpha.1`; reinstalar esa VERSION hacía `rsync --delete` sobre el código activo y `PREVIOUS == RELEASE` anulaba el rollback | test de contrato falla contra la base | sobrescritura en caliente sin rollback posible |
| 6 | Raíz de share ausente/desmontada ⇒ tombstone de todos los documentos | test | borrado masivo registrado ante un fallo de disco |
| 7 | Colisión de mayúsculas en el hub Linux (dos PCs offline), symlink o archivo que desaparece durante el hash detenían el observador completo | tests + laboratorio | caída de toda la ingesta |
| 8 | Archivo tocado sin cambio de contenido: SHA-256 recalculado (dos veces) cada 5 s | test con contador | CPU/IO continuos en archivos grandes |
| 9 | La API aceptaba shares con cualquier `local_root` (`/etc`, `/home`) | test | el observador archivaría rutas del sistema |
| 10 | `tests/test_content_store.py` fallaba ejecutado aislado (dependía del orden de la suite) | `pytest tests/test_content_store.py` | sólo desarrollo |

Hallazgos no corregidos (requieren decisión o gate físico): ver «Pendientes reales».

## Cambios realizados y por qué

- **Observador** (`file_watcher.py`, `local_cloud_worker.py`,
  `local_cloud_models.py`): hallazgos 2, 3, 6, 7, 8. `RECOVERED` sólo si el SHA
  coincide con el tombstone; contenido distinto en la misma ruta es `MODIFIED`.
  ENOSPC/EROFS/EIO siguen deteniendo el proceso (fallo sistémico visible).
  Preflight de escritura del ContentStore al arrancar; cada aviso se registra
  una vez, no cada ciclo.
- **API**: hallazgo 9 (`local_root` dentro de `SERVER_OFICINA_SYNC_ROOT`).
- **Instalador** (`install-tablet.sh`, `lib-release.sh`): hallazgos 4 y 5.
  Directorio `VERSION+fecha.gCOMMIT`, nunca reutilizado; crea `files/` y
  `versions/` sólo si faltan (sin `chown -R`); escribe `SYNC_ROOT` y
  `VERSIONS_ROOT`; conserva ajustes del operador en el env; no copia `.git` ni
  `.env`; activa el observador sólo tras health OK y exige `NRestarts=0`;
  rollback restaura el estado previo del observador. Se mantienen validación
  previa, venv, backup PostgreSQL con SHA, health check, symlink `current` y
  rollback.
- **Unidad local-cloud**: `ProtectSystem=strict`; `files/` es de sólo lectura
  para el observador por el sistema operativo; sólo `versions/` y `data/app`
  escribibles.
- **Paquete/CI**: hallazgo 1. `generate-manifest.sh --check` (detecta archivos
  no listados; orden `LC_ALL=C`); CI ejecuta frontend + despliegue + MANIFEST.
  Nuevo job `hub-worker-lab` (Syncthing v2.1.5 verificado por SHA-256 publicado).
- **Laboratorio**: `preparar-nube-local-lab.sh` usa `LAB_SYNC`, Syncthing del
  hub con usuario `serveroficina-sync` y puertos LAN; ya no crea carpetas de
  áreas reales ni hace `chown -R`.

## Pruebas automáticas (entorno cloud, commit `42dd3f1`)

| Gate | Resultado |
|---|---|
| pytest Python 3.12 | **144 passed** (base: 123) |
| pytest Python 3.13 | **144 passed** |
| `syntax-check.py` | `SYNTAX_OK (85 archivos)` (base: 82; el relevo decía 80) |
| `VALIDAR_SERVER_OFICINA.sh` copia limpia | `PACKAGE_OK` (base: `EXIT=1`) |
| Simulación de la ruta del instalador (rsync con exclusiones + `RELEASE_INFO` + `.venv` + `verify-package.sh` dentro de la release) | `PACKAGE_OK`; segunda instalación y release activa → `RELEASE_COLLISION` |
| `shellcheck -S warning` en scripts tocados | sin avisos |
| `systemd-analyze verify` unidades | sin directivas inválidas (sólo falta el ejecutable, esperado fuera de la Latitude) |
| Esquema alpha.2/3/4 → candidata | sólo tablas nuevas (47 desde alpha.2); 0 columnas nuevas/eliminadas/cambiadas en tablas existentes |
| Advertencia Starlette/AnyIO | persiste; no es fallo |

GitHub Actions sobre `42dd3f1`: **Syncthing Integration run 36282926808 ✅**
(`real-syncthing` con tres contenedores 2.1.5 y el nuevo `hub-worker-lab` con
binario verificado por SHA-256). `local-cloud-ci.yml` (Python 3.12/3.13 en
GitHub) **no se ejecutó** para esta rama: sólo se dispara con push a `agent/**`
o con un pull request; los resultados 3.12/3.13 de arriba son locales.

## Laboratorio nativo Syncthing real + observador (NO es gate físico)

Tres procesos Syncthing v2.1.5 (pc1 ↔ hub ↔ pc2) por loopback en un solo host
Linux y el observador real como proceso independiente sobre la carpeta del hub.
Sin Windows, sin Office, sin Wi-Fi. Resultado `HUB_WORKER_LAB_OK` en Python 3.12
y 3.13.

| Escenario | Resultado |
|---|---|
| crear `Inventario_LAB.xlsx` (openpyxl sintético) | hub 2,0 s; versión registrada 3,5 s; objeto en ContentStore |
| modificar | v1 y v2 verificables |
| renombrar / mover a subcarpeta | tombstone origen + documento nuevo, mismo SHA (sin vínculo de rename) |
| borrar `Binario_LAB.bin` (3 MiB) | tombstone; bytes en ContentStore y `.stversions` del hub |
| restaurar con mismo mtime | `RECOVERED`, documento vivo (en la base: nunca se registra) |
| restore desde historial Server Oficina | llega a pc1 en 1,5 s con SHA idéntico |
| hub apagado con cambio pendiente | converge 2,0 s tras arrancar |
| reinicio pc1 / reinicio del observador | converge; observador recupera en ~2 s |
| corte de red (pausa del hub en pc1) | nada llega durante el corte; converge 2,5 s tras reanudar |
| edición concurrente offline | ambas versiones preservadas; `CONFLICT_REVIEW`; ambas en ContentStore |
| `Radio.txt` / `radio.txt` en el hub | ambos en cuarentena, observador sigue vivo e ingiere otros archivos |
| recursos del observador | ~53 MiB RSS, 0,6 s CPU en toda la corrida |

## Gates físicos

| Gate | Estado |
|---|---|
| PRE Latitude | **NO ejecutado** (sin acceso) |
| Instalación controlada / POST | **NO ejecutado** |
| Gate 1 PC ↔ Latitude | **NO ejecutado** |
| Offline / Internet apagado | **NO ejecutado** |
| Reinicios físicos | **NO ejecutado** |
| Delete/restore físico | **NO ejecutado** (lógica corregida y probada en laboratorio) |
| Cambio Wi-Fi/DHCP | **NO ejecutado**; riesgo UFW por subred identificado |
| CPU/RAM/disco en la Latitude | **NO medido** |
| PostgreSQL / backup en la Latitude | **NO verificado** |

## Riesgos observados

- UFW permite 8080 (y en el laboratorio 22000/21027) sólo desde la subred
  vigente: un router con otra subred bloquea el acceso ⇒ gate de cambio de
  Wi-Fi fallaría. Decidir antes (p. ej. RFC1918 en la interfaz LAN).
- Última instalación física documentada: alpha.2 (2026-09-11). El salto es
  grande aunque el esquema sea aditivo; el backup pre-upgrade y el rollback no
  se han probado físicamente con esta candidata.
- Syncthing de Debian (hub) puede ser 1.x y la PC 2.x; CI sólo prueba 2.1.5.
- `backup.sh` no respalda `versions/` ni la identidad Syncthing del hub.
- Sin Companion, el hub no atribuye cambios a una PC (`source_peer_id` vacío).
- Releases fallidas o antiguas se acumulan en `/opt/server-oficina/releases`
  (cada una con su venv); no hay limpieza automática.
- El instalador requiere Internet (apt/pip); la operación no.

## Recomendación

**Todavía no avanzar al gate de 2 PCs.** Primero: fusionar estas correcciones
en la rama candidata (decisión del responsable), ejecutar el runbook 52 en la
Latitude (PRE → validar → instalar → POST → gate 1 completo) y decidir la
regla UFW por subred. Sólo con el gate 1 físico con evidencia completa tiene
sentido pasar a 2 PCs.
