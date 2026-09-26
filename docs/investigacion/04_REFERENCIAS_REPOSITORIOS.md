# 04 · Registro de referencias y repositorios

**Regla:** una referencia no equivale a una dependencia. Se documenta URL, snapshot revisado, patrón aprendido, adaptación y decisión de incorporación/descartes. Esta alpha contiene implementación original y no copia módulos de terceros.

## Proyectos propios: evidencia operativa que sí define requisitos

| Repositorio | Snapshot revisado | Qué aporta | Adaptación en Server Oficina |
|---|---|---|---|
| https://github.com/francisco-oos/Formatos-HSE-Campo | `0786c7d5a9c26e32a3f6e06ed26be662bad21e7d` + README actual revisado 2026-09-10 | Android/Kotlin, PDF, QR, JSON AES-256-GCM embebido, SHA-256, fotos, perfil operativo | Futuro adaptador HSE: el PDF permanece evidencia humana y el payload estructurado podrá producir eventos verificables. **No se integra todavía.** |
| https://github.com/francisco-oos/SupervisionSeguraManage | `abe5418b47d7b0e20818267a3f4be539075310e1` | extracción/descifrado del JSON, normalización, PDF original + payload + hashes | Patrón directo de procedencia/evidencia. En el futuro se trasladará el concepto a PostgreSQL/Tracking Core, no se incrusta la aplicación PySide6. |
| https://github.com/francisco-oos/Tendido-Diario-revision | `42da7d48bc0d7e722c81b7c9a665e9b2f37993e2` | conciliación Sercel/INOVA/comentarios, prioridad de fuentes, claves por punto, histórico y cambios | Referencia para Asset Core/Tracking Nodes y futuro adaptador de conciliación SERCEL/INOVA/comentarios. Alpha.3 implementa el timeline y operaciones; no copia el motor original. |
| https://github.com/francisco-oos/NodeHealthAnalyzer | `b7afbe41c0a7d7e458747e8afe271fc3c670d016` | importación masiva de CSV, histórico de nodos, analítica/mantenimiento | Referencia para `asset_health_observations` y mantenimiento. Alpha.3 almacena observaciones; el cálculo especializado continúa fuera del servidor. |
| https://github.com/francisco-oos/EventEstudio | baseline `a20066c2f5bb7b91d66434190bf10db1e4607334` | experiencia real con backend web, cuentas/roles, seguridad, restauración, regresiones, despliegue | Se adoptan **principios** de permisos, pruebas de regresión, backups/restore y no destruir datos. No se reutiliza su dominio ni DB. |

## Repositorios externos estudiados

| Repositorio | Snapshot observado | Patrón evaluado | Decisión |
|---|---|---|---|
| https://github.com/grokability/snipe-it | `8d285d254fcb03aaa2111872e19aaca6e1030c67` (observado 2026-09-10) | checkout/check-in, custodia, asset tags, historial, límites de alcance | **Estudiar/adaptar patrón. No copiar.** Licencia AGPL-3.0: mantener frontera legal clara. |
| https://github.com/allegro/ralph | `adbe619caba31425a6b28bd8913fed2500c2fd96` | lifecycle de activos/CMDB y back-office assets | Referencia de ciclo de vida/CMDB contrastada con Asset Core. No instalar Ralph como base del producto. |
| https://github.com/glpi-project/glpi | `5b3eadfa0a549877559e08e6e5a13047c380aace` | activos/configuración, ubicación, incidencias/solicitudes | Estudiar separación activo/incidencia/configuración. No adoptar suite completa. |
| https://github.com/openboxes/openboxes | `635b225b0dfc0d07619dad1a6583fbd9d803d5f4` | inventario y movimientos de stock | Estudiar movimientos/ubicaciones para Control de Material y cierre de proyecto. No dependencia. |
| https://github.com/apache/casbin-node-casbin | `aad42ce2be70908bbc76c5b89b505cf0655245e8` | RBAC/ABAC/policy engine | No se integra en 0.1; RBAC propio es pequeño y auditable. Revaluar si las políticas crecen. |
| https://github.com/fastapi/full-stack-fastapi-template | `cb740b656d7a0a6c5e12c7bf8e50343ec94ee9c7` | arquitectura FastAPI/PostgreSQL, testing y separación web/API | Referencia de stack y prácticas; esta implementación se escribió específicamente para Server Oficina, sin copiar el template. |

## Infraestructura inventariada para futuro

Estas referencias ya estaban registradas en la biblioteca técnica y se mantienen como opciones, **no como componentes de la alpha**:

- https://github.com/tailscale/tailscale — acceso remoto privado futuro;
- https://github.com/juanfont/headscale — control plane self-hosted futuro;
- https://github.com/rclone/rclone — copias/exportaciones a destinos externos;
- https://github.com/syncthing/syncthing — archivos/datasets, explícitamente **no** DB viva;
- https://github.com/microsoft/playwright — E2E web cuando se cierre la UI física/LAN.

## Política de mantenimiento de referencias

Antes de tomar código de una referencia futura:

1. fijar commit/tag exacto;
2. revisar licencia vigente;
3. documentar archivos/patrones concretos que se pretenden adaptar;
4. justificar por qué aporta frente a implementación propia;
5. añadir pruebas de comportamiento;
6. registrar en CHANGELOG/NOTICE y este documento.


## Investigación añadida en alpha.2

| Fuente | Uso conceptual | Decisión |
|---|---|---|
| ISO 55000:2024 · https://www.iso.org/standard/83053.html | gestión del activo durante ciclo de vida, valor y objetivos | referencia conceptual; no se redistribuye texto normativo |
| ISO 14224:2016 · https://www.iso.org/standard/64076.html | taxonomía de equipo/falla/mantenimiento/downtime | adaptar categorías útiles al dominio sísmico; no afirmar conformidad ISO |
| ISO 17359:2018 · https://www.iso.org/standard/71194.html | estructura de programa de monitoreo de condición | usar como referencia para separar observación/diagnóstico/pronóstico |
| ISO 13379-1:2025 · https://www.iso.org/standard/88027.html | interpretación de datos y diagnóstico de condición | referencia conceptual; no copiar texto normativo |
| ISO 13381-1:2025 · https://www.iso.org/standard/88029.html | procesos de pronóstico y datos necesarios | RUL futuro con método/versión/confianza/procedencia, nunca verdad estática |
| GS1 EPCIS 2.0 · https://www.gs1.org/standards/epcis | eventos de trazabilidad qué/cuándo/dónde/contexto | inspiración para contratos de evento; no dependencia |
| HR Open Standards · https://www.hropenstandards.org/standards-downloads | vocabularios de persona/trabajo/organización e interoperabilidad | estudio; conservar modelo propio |
| HROpen/APISpecifications `707ec7d3741df46f6973411e5dd75c756cf3d7d7` | Workers/Organizations/Jobs | estudio solamente; repo no declara licencia en metadata, revisar términos antes de copiar |
| STPS SIRCE · https://www.gob.mx/stps/acciones-y-programas/stps-04-002-presentacion-de-listas-de-constancias-o-de-competencias-laborales | contexto de planes/cursos/constancias de capacitación | orientar campos/evidencia, no prometer cumplimiento ni envío automático |
| NOM-017-STPS-2024 · https://dof.gob.mx/normasOficiales/9496/stps/stps.html | ciclo de EPP: selección, uso, revisión, reposición, mantenimiento, resguardo, disposición | informar roadmap EPP/Asset; sin motor legal automático |

Detalle de investigación: `docs/investigacion/12_INVESTIGACION_CICLO_VIDA_ACTIVOS.md` y `docs/investigacion/13_INVESTIGACION_RRHH_OPERATIVO.md`.

## Evidencia operativa interna

La release sólo conserva metadatos y conclusiones de diseño de documentos propios revisados; no empaqueta sus datos sensibles. Ver `docs/arquitectura/18_EVIDENCIA_OPERATIVA_Y_TRAZABILIDAD_DE_FUENTES.md` y `references/internal_evidence.json`.


## Sincronización, navegación y agentes estudiados en 0.2

| Fuente | Patrón aprendido | Decisión |
|---|---|---|
| https://github.com/syncthing/syncthing | Device ID, version vectors, bloques, descubrimiento local, conflictos y REST API | **Adoptado como transporte HOT**, nunca como fuente de verdad ni auditoría humana |
| https://github.com/bcpierce00/unison | reconciliación contra ancestro/archivo previo | patrón para BASE/LEFT/RIGHT; no segundo motor sobre la misma carpeta |
| https://github.com/mutagen-io/mutagen | two-way-safe, scan/reconcile/stage/apply | adoptar fail-safe y separación de fases; no dependencia |
| https://github.com/rclone/rclone | bisync preflight/check-access y VFS cache/read-ahead | patrones para adapter NAS, caché y límites de daño; no sincronizador concurrente del árbol HOT |
| https://github.com/nextcloud/desktop | conflicto explícito y archivos virtuales | referencia UX; no desplegar una segunda plataforma |
| https://github.com/haiwen/seafile-client | conflicto preservado y experiencia de locking | referencia UX/coord. de edición |
| https://github.com/tus/tusd | cargas HTTP reanudables por sesión/offset | referencia para subida directa PC→NAS; aún no dependencia |
| https://github.com/microsoft/Windows-classic-samples/tree/main/Samples/CloudMirror | CFAPI, sync root, placeholders e hidratación | prototipo de referencia para futuro Companion Windows; la muestra no es código productivo |
| https://github.com/ajeetdsouza/zoxide | frecency y ranking de rutas usadas | inspiración para Smart Navigator; no sirve como buscador de contenido documental |
| https://github.com/NousResearch/hermes-agent | runtime de agente, herramientas, skills, memoria/learning loop y backends aislables | estudiar separación Agent Runtime/Tool Registry/Skills; **no** convertir su memoria del agente en verdad de oficina |
| https://github.com/tus/tusd | pausa/reanudación sin retransmitir lo ya confirmado | semántica adoptada en `ContentTransfer`; backend físico aún por implementar |
| https://git-annex.branchable.com/ | contenido por hash, ubicación distribuida, preferred/required content, numcopies/mincopies y drop seguro | adoptar guardas de réplica y política de ubicación; no exponer Git al usuario |
| https://github.com/git-lfs/git-lfs | puntero pequeño OID+size, objetos grandes externos, Batch API y locks | patrón para identidad lógica separada de ubicación; no dependencia Git |
| https://github.com/automerge/automerge | CRDT local-first y merge de estado estructurado | candidato futuro sólo para datos nativos colaborativos; no para fusionar Office binario |

El detalle de sincronización está en
`docs/investigacion/46_INVESTIGACION_SINCRONIZACION_ROBUSTA.md` y
`docs/investigacion/47_ALMACENAMIENTO_JERARQUICO_ARCHIVOS_GRANDES.md`.

La separación Core/Domain Pack se gobierna en
`docs/vision/49_NUCLEO_REUTILIZABLE_Y_DOMAIN_PACKS.md`.

### Snapshots externos revisados en esta fase

| Repositorio | Commit revisado |
|---|---|
| `syncthing/syncthing` | `94c3c1cdef718d568686620cbff268eeaaf2c87d` |
| `mutagen-io/mutagen` | `6ccfeaaf4dfd261e59ef9aac56e3c157b62e605b` |
| `rclone/rclone` | `9dc8b71ae99496460f07373674609571918bfb9c` |
| `ajeetdsouza/zoxide` | `09a18b4424b3f1033094ffd97da6d47585e38259` |
| `NousResearch/hermes-agent` | `f077152871798b8a666daf48333d123549d10672` |
| `tus/tusd` | `c9d174d0e20c69f24e9785d2f639df4da1c4fdc5` |
| `git-lfs/git-lfs` | `0043a645047926f4bd7f7091299095528253d575` |
| `automerge/automerge` | `ddbff535407e4d28cd2a82eaf6c6add08caa3bdd` |

Los commits sólo fijan el punto estudiado; no implican dependencia ni copia de código.
