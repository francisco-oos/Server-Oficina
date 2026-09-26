# 51 · Arquitectura Synology, archivos pesados y acceso transparente

Fecha: 2026-09-26.

## Objetivo

Evitar que cada archivo exista obligatoriamente en PC + Latitude + NAS, sin
romper la experiencia de «una sola carpeta de Server Oficina».

La ubicación física deja de ser identidad:

```text
DocumentVersion
  └─ SHA-256 + tamaño
       └─ ContentLocation
            ├─ repositorio LOCAL/HUB
            ├─ repositorio SMB/NAS
            └─ futuros backends
```

`EvidenceRepository` sigue siendo el catálogo canónico de almacenamiento ya
existente. Nube Local sólo le agrega `StorageRepositoryProfile`; no existe un
segundo catálogo paralelo de endpoints.

## Hallazgos Synology relevantes

### Synology Drive On-demand Sync

Synology Drive Client ofrece sincronización a petición en Windows 10 1809+ sobre
NTFS. Los archivos pueden permanecer visibles en Explorer sin conservar todos
sus bytes localmente.

Esto valida la UX que buscamos, pero **no se adopta Synology Drive en cada PC
como dependencia del Core**. Queremos que el NAS pueda reemplazarse sin cambiar
el cliente ni el dominio.

Además, una raíz On-demand no debe superponerse con otras raíces de archivos a
petición como OneDrive/iCloud/Synology Drive. El Companion deberá registrar su
propio sync root de forma controlada cuando llegue la fase CFAPI.

### Bloqueo de archivos en Synology Drive

Drive permite locking manual y, en Windows con On-demand Sync, auto-lock para
Microsoft Office/AutoCAD abiertos con sus aplicaciones nativas.

El límite importante es que **el lock de Synology Drive sólo gobierna accesos
hechos a través de Synology Drive**. Si otro usuario entra por SMB, File Station
u otro protocolo, ese lock no es autoridad universal.

Por eso Server Oficina mantiene `FileLease` como coordinación transversal.

### SMB3, leases y durable handles

DSM soporta Opportunistic Locking, SMB2 file leases y durable handles. Los
durable handles ayudan a retomar archivos abiertos después de una interrupción
temporal de red.

Esto hace que SMB3 sea el candidato más simple para un primer camino directo
PC→NAS cuando el NAS está en la misma LAN. Aun así:

- la copia se escribe primero a staging/archivo temporal;
- `ContentTransfer.confirmed_offset` conserva progreso lógico;
- al terminar se verifica tamaño + SHA-256;
- sólo después se promociona el nombre final;
- `FileLease` sigue siendo la coordinación de Server Oficina;
- opciones SMB concretas se validarán contra el Synology real antes de fijarlas.

### File Station API

La API oficial de File Station permite upload a rutas de carpetas compartidas y
control de overwrite. La documentación revisada no aporta por sí sola la
garantía de reanudación por offset que exigimos para varios GB.

Conclusión: no se elige como transporte principal de archivos pesados hasta
probar recuperación de una transferencia cortada.

## Estrategia elegida por fases

### Fase A — ahora

```text
archivos HOT de oficina
PC ⇄ Syncthing ⇄ Latitude

archivos NAS ya existentes
NAS/SMB ⇄ montaje Latitude ⇄ EvidenceRepository
```

Excel, Word, PDF y formatos de trabajo cotidianos siguen replicados de forma
local-first.

### Fase B — archivo grande directo

Cuando una política indique `NAS_DIRECT`:

```text
PC Companion
  ├─ registra intención/version en Server Oficina
  └─ escribe bytes directo a staging del NAS
       └─ resume desde offset confirmado
            └─ verifica SHA-256/tamaño
                 └─ rename/promoción atómica
                      └─ ContentLocation = AVAILABLE
```

El objetivo es evitar:

`PC → Latitude SSD → NAS`

cuando el mismo archivo puede viajar:

`PC → NAS`

sin perder trazabilidad.

### Fase C — namespace transparente

El Companion Windows evolucionará a sync provider con Microsoft Cloud Files
API (CFAPI):

- placeholder visible en Explorer;
- identidad opaca ligada a DocumentVersion;
- hidratación al abrir;
- pin «Mantener siempre disponible»;
- deshidratación de caché sólo cuando ReplicaGuard lo permita;
- origen elegido por Content Resolver.

Microsoft documenta placeholders de aproximadamente 1 KB y políticas de
hidratación FULL/PROGRESSIVE/PARTIAL, además de callbacks de fetch/close/delete/
rename. Eso permite que una ruta se vea normal aunque el byte esté en NAS.

No se implementará CFAPI a medias mediante archivos `.url` o accesos directos
que rompan aplicaciones Office.

## Un namespace físico, un transporte

Nunca se deja que Syncthing y el adapter NAS escriban simultáneamente sobre el
mismo path físico.

- carpeta HOT física → Syncthing;
- staging NAS_DIRECT → adapter NAS;
- vista lógica unificada → Content Resolver / Companion.

Esto evita carreras, doble subida y loops.

## Política configurable, no umbral hardcodeado

Ejemplo conceptual:

```json
{
  "selector": {
    "extensions": [".mp4", ".zip"],
    "min_size_bytes": 1073741824
  },
  "action": {
    "mode": "NAS_DIRECT",
    "repository_code": "NAS_OFICINA"
  }
}
```

El número es sólo un ejemplo de configuración. El código no contiene un tamaño
universal.

También puede decidir por:

- familia documental;
- área;
- frecuencia de acceso;
- capacidad libre;
- criticidad/offline;
- tipo MIME.

## Eviction seguro

Una caché sólo puede liberarse cuando:

1. existe al menos el número de copias verificadas exigidas;
2. están en repositorios físicos distintos;
3. los repositorios obligatorios están presentes;
4. hash y tamaño coinciden con DocumentVersion;
5. la versión no está pinned.

Dos rutas dentro del mismo NAS cuentan como **una sola réplica física**.

## Acceso y usuarios

Todos los usuarios autorizados pueden seguir documentos de cualquier área. El
`owner_area_code` determina procedencia/autoridad del dato, no invisibilidad.

La sesión de estación dura hasta 15 días para atribución de operador. La
presencia «online ahora» requiere heartbeat reciente y es una señal adicional a
RRHH, nunca un reemplazo de su estado oficial.

## Riesgos que deben probarse físicamente

- NAS cae durante una carga grande;
- Wi-Fi cambia durante transferencia;
- SMB reconecta tras pérdida temporal;
- archivo queda parcialmente escrito;
- NAS lleno;
- hash final incorrecto;
- dos PCs intentan cargar el mismo destino;
- una copia cacheada se intenta expulsar siendo la última;
- Synology Drive/SMB y FileLease muestran estados contradictorios;
- placeholder se abre cuando NAS y hub no están disponibles.

## Fuentes

- Synology Drive Client:
  https://kb.synology.com/es-mx/PAS/help/SynologyDriveClient/synologydriveclient?version=1_0
- Synology Drive Admin Console / file locking:
  https://kb.synology.com/index.php/es-mx/DSM/help/SynologyDrive/drive_admin_console?version=7
- Synology SMB settings:
  https://kb.synology.com/index.php/es-mx/DSM/help/SMBService/smbservice_smb_settings?version=7
- Synology File Station API:
  https://global.download.synology.com/download/Document/Software/DeveloperGuide/Package/FileStation/All/enu/Synology_File_Station_API_Guide.pdf
- Microsoft Cloud Files API:
  https://learn.microsoft.com/windows/win32/cfapi/cloud-files-api-portal
- Microsoft placeholder sync engine:
  https://learn.microsoft.com/windows/win32/cfapi/build-a-cloud-file-sync-engine
