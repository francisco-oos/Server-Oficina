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
- cache LRU/por política sólo para contenido WARM;
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
- purge sólo cuando existe política y suficientes réplicas verificadas.

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
