# 47 · Investigación — almacenamiento jerárquico, archivos grandes y acceso transparente

Fecha: 2026-09-26.

## Problema

Replicar cada byte de cada documento en todas las PCs, Latitude y Synology
produce redundancia, usa SSD innecesariamente y puede retrasar sincronizaciones
cuando existen videos, imágenes, respaldos u otros archivos pesados.

El objetivo no es «copiar todo en todas partes», sino que el usuario vea un
**espacio lógico único** y Server Oficina conozca dónde existe cada versión.

## Hallazgos

### Syncthing

Syncthing mantiene versiones mediante version vectors y transfiere sólo los
bloques requeridos. Su protocolo describe hashes por bloque y tamaños de bloque
adaptables; esto evita reenviar necesariamente un archivo completo cuando
existen bloques reutilizables. Los conflictos concurrentes se preservan como
copias `.sync-conflict`.

Conclusión: excelente transporte para el conjunto **HOT** que sí queremos
replicado entre PC y hub; no debe obligarnos a replicar todo el archivo frío.

### Mutagen

Su modo `two-way-safe` usa reconciliación de tres vías y sólo auto-resuelve
cuando no destruye datos no sincronizados. Además separa watcher, scan,
staging y apply.

Conclusión: adoptar la filosofía **scan/reconcile/stage/apply** y fail-safe, no
añadir Mutagen como segundo motor sobre la misma carpeta.

### rclone bisync

Aporta ideas de `check-access`, bloqueo de corridas, comparación por checksum,
abortado por borrado excesivo y entrada en estado seguro.

Conclusión: adoptar preflight, health markers y límites de daño para el canal
hub→NAS.

### Windows Cloud Files API (CFAPI)

Windows permite registrar un sync root con archivos placeholder. Un placeholder
ocupa prácticamente sólo metadatos y puede hidratarse cuando una aplicación lo
abre. También existen estados de archivo completo, descargable y fijado para
uso offline.

Conclusión: para la experiencia verdaderamente imperceptible con archivos muy
grandes, el camino nativo a largo plazo es que el Companion Windows actúe como
**sync provider** mediante CFAPI, no crear accesos directos .url como solución
final.

### Synology Drive On-demand Sync

Synology ya demuestra el mismo patrón: archivos visibles en Explorer sin
mantener todos sus bytes locales y posibilidad de fijarlos offline. También
ofrece bloqueo automático de Office en ciertas condiciones.

Conclusión: estudiar la UX y semántica; no hacer que las PCs dependan
directamente de Synology Drive porque queremos que Server Oficina siga siendo
la capa estable y el NAS sea reemplazable.

### SMB leases

SMB usa leases/oplocks para coordinar caché, escritura y handles abiertos. Es
útil para archivos abiertos directamente sobre un servidor, pero no sustituye
la copia offline.

Conclusión: sus estados READ/WRITE/HANDLE inspiran nuestro FileLease, pero la
arquitectura local-first no se convierte en un simple share SMB.

### rclone VFS

El VFS de rclone demuestra otra separación útil: namespace remoto, caché local,
write-back y descarga por rangos. En modo `full` puede usar archivos dispersos
y conservar sólo las zonas realmente leídas; además expulsa caché según edad,
espacio máximo y último acceso.

Conclusión: adoptar **cache budget + LRU/last-access + read-ahead configurable**,
pero no montar rclone encima de la misma carpeta sincronizada por Syncthing.

### tus / cargas reanudables

El protocolo tus modela una carga grande mediante URL de sesión y
`Upload-Offset`. Si una red cae, el cliente pregunta el offset y continúa
desde allí en vez de reiniciar gigabytes desde cero. También define extensión
de checksum por fragmento.

Conclusión: la futura ruta directa PC→NAS debe tener semántica de transferencia
reanudable e idempotente. Si el backend NAS no la ofrece nativamente, se
implementa en el adapter; no se vuelve a copiar el archivo entero por una caída.

### rsync / delta

El algoritmo rsync usa checksum rodante + checksum fuerte para localizar bloques
reutilizables incluso si se desplazaron dentro del archivo.

Conclusión: es una referencia para deltas grandes, pero **no se reimplementa**
dentro de Server Oficina mientras Syncthing ya resuelva el transporte HOT por
bloques. Sólo se justificaría otro delta engine en un adapter NAS que demuestre
una necesidad medible.

### git-annex

git-annex aporta un concepto muy cercano al problema real: la identidad del
contenido se separa de la ubicación física y cada repositorio puede declarar
qué contenido prefiere o exige conservar. Sus reglas `numcopies`,
`mincopies`, preferred/required content y el rechazo de `drop` cuando no se
pueden verificar suficientes copias son especialmente útiles.

Conclusión: Server Oficina no adoptará git-annex como motor del usuario, pero sí
su invariante más valiosa: **no expulsar/purgar una copia si no se verificó que
quedan las réplicas exigidas por política**.

### Git LFS

Git LFS mantiene en el repositorio un puntero pequeño con OID SHA-256 y tamaño,
mientras los bytes grandes viven en otro servicio. Su Batch API negocia la
ubicación/acción concreta para upload/download y su API de locking separa
reservas de archivo del transporte.

Conclusión: `DocumentVersion + ContentLocation` cumple un papel equivalente al
puntero lógico: la interfaz trabaja con identidad/hash/tamaño y el
`Content Resolver` decide el backend. No se adopta Git ni LFS como requisito
operativo.

### CRDT / Automerge

Los CRDT pueden combinar cambios concurrentes a estructuras finas y conservar
conflictos de propiedades. Son excelentes para datos nacidos dentro de una app
local-first.

Conclusión: pueden ser útiles más adelante para notas, formularios o estado de
interfaz nativo de Server Oficina. **No solucionan de forma segura la edición
concurrente de un XLSX/DOCX binario arbitrario**; para esos archivos se conserva
lease + versiones + conflicto + revisión/merge semántico conocido.

## Arquitectura propuesta: almacenamiento por niveles

```text
ESPACIO LÓGICO "Server Oficina"
             │
             ▼
        Content Resolver
             │
   ┌─────────┼──────────┐
   ▼         ▼          ▼
HOT       WARM/CACHE   COLD
PC/local  Latitude     NAS/Synology
```

Cada versión puede tener cero o más ubicaciones físicas verificadas. La
identidad es su documento/versión/hash, no la ruta física.

Estados mínimos:

- `LOCAL_FULL`: bytes completos en la PC.
- `LOCAL_PINNED`: se exige disponibilidad offline.
- `PLACEHOLDER`: namespace local, bytes bajo demanda.
- `HUB_CACHE`: copia temporal/operativa en Latitude.
- `NAS_PRIMARY`: contenido verificado en almacenamiento de capacidad.
- `PENDING_TRANSFER`: transferencia aún no confirmada.
- `UNAVAILABLE`: se conoce la versión, pero ningún origen está disponible.

## Regla importante

No se define un umbral mágico hardcodeado como «500 MB». La política depende
de tipo de archivo, área, capacidad, frecuencia de acceso y disponibilidad de
NAS. Se configura como dato.

Ejemplos:

- Excel operativo diario → HOT / disponible offline.
- PDF histórico normal → HOT o WARM según política.
- video de evidencia de varios GB → NAS_PRIMARY + placeholder.
- archivo crítico marcado «Mantener sin conexión» → LOCAL_PINNED aunque sea grande.

## Subida directa de archivos pesados

Para evitar PC → Latitude → NAS duplicando tráfico y espacio:

```text
PC
├─ metadatos/intent ─────────────► Server Oficina
└─ bytes ───────────────► NAS endpoint autorizado
                           │
                           └─ hash/tamaño verificados
                                  │
                                  ▼
                             Server Oficina
                             registra ubicación
```

El servidor sigue siendo autoridad sobre identidad, permisos, versión y
provenance. El NAS sólo aloja bytes.

Si el NAS no está disponible, la política decide entre:
- dejar el archivo pendiente en la PC;
- usar temporalmente el hub si hay capacidad;
- exigir «Mantener local».

Nunca se anuncia disponibilidad que no existe.

## Acceso transparente

El usuario debe abrir siempre el mismo elemento lógico. El Content Resolver
prefiere:

1. copia local verificada;
2. caché del hub;
3. NAS accesible;
4. hidratación bajo demanda;
5. error explícito con causa si ninguna ubicación está disponible.

Un placeholder no es una promesa mágica: sin NAS/hub disponible y sin caché
local, el archivo no puede abrirse. La interfaz debe mostrar ese estado antes de
que el usuario pierda tiempo.

## Evitar redundancias

- deduplicación por SHA-256 para versiones idénticas;
- no guardar dos copias en Latitude del mismo contenido;
- usar bloques del motor de transporte, no inventar otro protocolo;
- cargas grandes directas deben ser reanudables por offset/chunk;
- cache LRU/por política sólo para contenido WARM;
- read-ahead y caché por rangos sólo cuando el backend/placeholder lo soporte;
- separar metadatos permanentes de bytes cacheables;
- Synology no replica de vuelta contenido que ya es NAS_PRIMARY salvo que una
  política pida caché/pin.

## Seguridad e integridad

- toda ubicación se registra con hash y tamaño esperado;
- transferencia primero a staging/`.partial`;
- promoción atómica;
- verify después de copiar;
- escritura directa al NAS usa destino temporal y rename/promote;
- credenciales de NAS fuera de BD y repo;
- borrado lógico separado de purge físico;
- purge sólo cuando existe política y suficientes réplicas verificadas;
- la política puede exigir `min_verified_copies` y endpoints obligatorios;
- una ubicación conocida pero no verificada no cuenta como copia segura.

## Referencias

- Syncthing BEP: https://docs.syncthing.net/specs/bep-v1.html
- Syncthing syncing/conflicts: https://docs.syncthing.net/users/syncing
- Syncthing versioning: https://docs.syncthing.net/users/versioning.html
- Mutagen synchronization: https://mutagen.io/documentation/synchronization
- Mutagen staging: https://mutagen.io/documentation/synchronization/staging
- rclone bisync: https://rclone.org/bisync/
- Microsoft Cloud Files API: https://learn.microsoft.com/windows/win32/cfapi/cloud-files-api-portal
- Cloud sync engine/placeholder guide: https://learn.microsoft.com/windows/win32/cfapi/build-a-cloud-file-sync-engine
- SMB lease algorithm: https://learn.microsoft.com/openspecs/windows_protocols/ms-smb2/d8df943d-6ad7-4b30-9f58-96ae90fc6204
- Synology Drive On-demand Sync: https://kb.synology.com/
- rclone VFS cache: https://rclone.org/commands/rclone_mount/
- tus protocol: https://tus.io/protocols/resumable-upload
- tusd reference server: https://github.com/tus/tusd
- rsync algorithm: https://rsync.samba.org/tech_report/
- Microsoft CloudMirror sample: https://github.com/microsoft/Windows-classic-samples/tree/main/Samples/CloudMirror
- git-annex preferred/required content: https://git-annex.branchable.com/git-annex-preferred-content/
- git-annex copies/drop safety: https://git-annex.branchable.com/copies/
- Git LFS specification: https://github.com/git-lfs/git-lfs/blob/main/docs/spec.md
- Git LFS locking API: https://github.com/git-lfs/git-lfs/blob/main/docs/api/locking.md
- Automerge conflicts/local-first: https://automerge.org/docs/reference/documents/conflicts/
