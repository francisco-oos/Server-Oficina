# POST — Server Oficina 0.2 · Fase 1 Nube Local / Sync Core

Fecha de actualización: 2026-09-26.

## Estado

Candidato de laboratorio. **No se promueve a producción todavía.**

Head verificado antes de este reporte: `e35f5804e4ab98f6fd3735d1e0ccd6e5cc629acd`.

- Server Oficina CI: verde en Python 3.12 y 3.13.
- Suite: 122 pruebas alcanzan 100 % en ambos runtimes.
- Sintaxis: 80 archivos.
- Syncthing Integration: verde con tres procesos Syncthing reales.
- Sigue una advertencia deprecada de Starlette/AnyIO; no rompe la suite.

## Implementado en esta fase

### Transporte y conflictos

- topología estrella `PC ↔ hub ↔ PC`;
- Syncthing como transporte HOT, no como base de datos ni auditoría;
- Device ID independiente de IP;
- versionado remoto y conflictos preservados;
- reconocimiento de `.sync-conflict-...`;
- conflictos bloqueados para análisis documental ordinario;
- nombres portables Windows/Linux y detección case/Unicode;
- temporales Office/Syncthing ignorados;
- FileLease cooperativo;
- merge semántico 3-way sólo para familias conocidas.

### Evidencia e historial

- `ContentStore` inmutable por SHA-256;
- copia temporal + fsync + hash/tamaño + promoción atómica;
- un borrado de la carpeta de trabajo no borra una versión ya capturada;
- restauración verificable desde historial.

### Identidad de estación

- identidad persistente de PC;
- credencial de dispositivo almacenada sólo como hash;
- sesión humana renovable como máximo cada 15 días;
- eventos offline idempotentes;
- atribución humana sólo dentro de una sesión válida;
- heartbeat reciente separado de la vigencia del login;
- presencia digital explícitamente distinta del estado oficial de RRHH.

### Visibilidad documental

Los usuarios autorizados pueden consultar transversalmente documentos de todas
las áreas. `owner_area_code` expresa procedencia/autoridad, no invisibilidad.

### Almacenamiento jerárquico

Se eliminó una duplicación conceptual detectada durante la revisión:
`EvidenceRepository` es ahora el catálogo canónico de almacenamiento.

Nube Local agrega:

- `StorageRepositoryProfile`: capacidades y prioridades;
- `StorageRepositoryHealth`: salud runtime ONLINE/DEGRADED/OFFLINE;
- `ContentLocation`: ubicación verificable de una DocumentVersion;
- `StoragePolicy`: reglas configurables HOT/NAS_DIRECT;
- `ContentTransfer`: sesión reanudable por offset;
- `ReplicaGuard`: no expulsar caché si faltan réplicas seguras;
- `Content Resolver`: local/hub/NAS sin acoplar la interfaz a la ruta física;
- `Storage Planner`: decide HOT o NAS_DIRECT usando políticas y salud reciente.

Una política NAS_DIRECT no provoca fallback silencioso al SSD de la Latitude:
si el NAS no está disponible o no soporta carga directa, el resultado es
`KEEP_LOCAL_PENDING_NAS`.

### Robustez NAS

Se añadió circuit breaker de disponibilidad. Un repositorio que falló varias
veces o cuyo último probe ONLINE envejeció deja de anunciarse como alcanzable.

Las operaciones de red deben ejecutarse fuera del request HTTP interactivo para
que un CIFS/SMB colgado no congele el dashboard.

### Investigación aplicada

Se contrastaron patrones de:

- Syncthing;
- Unison;
- Mutagen;
- rclone bisync/VFS;
- SMB leases/durable handles;
- Synology Drive On-demand/file locking;
- Windows Cloud Files API/CFAPI;
- tus resumable uploads;
- rsync;
- git-annex;
- Git LFS;
- Automerge/CRDT;
- restic/Borg content-defined chunking;
- zoxide;
- Hermes Agent.

Decisión importante: no construir un chunk store CDC propio en Fase 1. Syncthing
resuelve transporte HOT y el NAS resuelve capacidad. Borg/restic sólo se
revaluarán si métricas reales muestran que el historial pesado desperdicia
espacio.

## Pruebas reales que ya corren

El laboratorio CI levanta tres Syncthing 2.1.5 reales:

```text
pc1 ↔ hub ↔ pc2
```

Verifica:

- create/modify/rename/delete;
- versionado remoto;
- hub offline;
- ediciones concurrentes offline;
- supervivencia de ambos contenidos;
- reinicio de peer;
- lote de 100 archivos;
- transferencia de 4 MiB con SHA idéntico.

La suite también prueba:

- 24 clientes lógicos y 276 pares concurrentes;
- sesiones de usuario/PC;
- paths incompatibles Windows/Linux;
- ContentStore/restore;
- conflictos;
- política de ubicación;
- reanudación de transferencia;
- restart durante VERIFYING sin retransmitir;
- réplicas mínimas;
- dos rutas en un NAS cuentan como una réplica física;
- NAS OFFLINE/health check vencido;
- planificación NAS_DIRECT sólo con destino capaz y recientemente ONLINE;
- visibilidad documental transversal;
- estructura organizada de documentación.

## Hallazgos reales encontrados por los gates

Los tests han encontrado, entre otros:

1. datetime naive/aware SQLite vs PostgreSQL en leases;
2. códigos de PC sensibles a mayúsculas;
3. UID host/contenedor en el laboratorio Syncthing;
4. intento de contar rutas duplicadas del mismo NAS como réplicas diferentes;
5. inicialización `None` del primer contador de fallos del circuit breaker;
6. políticas de almacenamiento solapadas en tests, corregidas aislándolas por
   familia documental.

Se corrigieron antes de continuar.

## Documentación

La raíz de `docs/` quedó reducida a tres puntos de entrada. La documentación
vive por responsabilidad en `vision/`, `arquitectura/`, `decisiones/`,
`investigacion/`, `dominios/`, `interfaz/`, `seguridad/`, `pruebas/`,
`operacion/`, `desarrollo/` y `estado/`.

El layout tiene prueba automatizada para impedir volver a saturar la raíz.

## Pendiente antes de lectores/LLM

- Companion Windows real;
- discovery mDNS/DNS-SD físico;
- gate 1 PC Windows + Latitude;
- luego 2 y 5 PCs;
- cambio real de Wi-Fi/DHCP;
- Internet apagado;
- Office concurrente real;
- Synology real;
- corte/reanudación de archivo grande real;
- NAS lleno/caído durante staging;
- restore integral;
- CFAPI/placeholders;
- extracción progresiva del dominio sísmico a Domain Pack.

La inteligencia documental no debe adelantarse a estos gates de infraestructura.
