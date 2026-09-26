# 46 · Investigación extensa — sincronización robusta, colisiones e identidad de estación

Fecha de corte: 2026-09-26.

## Pregunta de diseño

Server Oficina necesita que las computadoras de la oficina trabajen con copias
locales normales, puedan quedar temporalmente offline, vuelvan a converger por
LAN y no dependan de la IP, del Wi-Fi concreto ni del Synology. La Latitude es
el primer hub; en el futuro ese rol debe poder migrar a otro servidor/NAS.

La sincronización no debe confundirse con auditoría, backup ni conocimiento de
negocio. Son capas distintas.

## Criterios evaluados

- Windows ↔ Linux y copias locales reales;
- operación sin Internet;
- sincronización continua, no sólo batch;
- identidad de dispositivo independiente de IP;
- conservación no destructiva de conflictos;
- API/control headless;
- comportamiento ante edición concurrente;
- recuperación ante borrados/reemplazos;
- coste operativo razonable para Latitude 7220;
- capacidad de evolucionar a otro hub sin rehacer el dominio;
- compatibilidad con un companion que atribuya operaciones a usuarios.

## Sistemas y patrones estudiados

| Sistema/patrón | Qué aporta | Qué no resuelve para Server Oficina | Uso |
|---|---|---|---|
| Syncthing | réplica continua P2P, IDs criptográficos, descubrimiento local, version vectors, bloques, conflictos preservados, REST API | no sabe qué humano editó, no es backup, no hace merge semántico de Office | **motor de transporte** |
| Unison | reconciliación contra archivo/estado anterior y detección de falsos conflictos | modelo más orientado a reconciliaciones de pares/sesiones | patrón para comparar BASE vs réplicas |
| Mutagen | modo two-way-safe que evita resolver conflictos con pérdida | orientado sobre todo a flujos de desarrollo | patrón de política fail-safe |
| rclone bisync | historiales de ambos lados, check-access, bloqueo, preservación de conflictos, controles contra borrados excesivos | sincronización por corridas; su propia documentación exige cuidado por riesgo de pérdida | patrón de preflight/safe-state |
| Nextcloud Desktop | copias locales, servidor central y conflicto explícito | plataforma completa adicional; duplica mucho de nuestro backend | referencia UX |
| Seafile | conflictos preservados y locking en edición | plataforma adicional; locking completo es parte de otra solución | referencia de conflicto/lease |
| SMB | leases/oplocks y bloqueo de archivo alojado en servidor | no ofrece por sí solo la copia local offline que pedimos | inspiración para FileLease |
| Windows ReadDirectoryChangesW | eventos rápidos de crear/renombrar/borrar/escribir | requiere proceso vivo; puede perder contexto tras parada | watcher rápido del companion |
| Windows USN Journal | registro NTFS durable de cambios del volumen y cierre de archivo | sólo NTFS/Windows y exige lógica adicional | recuperación de eventos del companion |
| Git 3-way | ancestro común BASE/LEFT/RIGHT y conflicto explícito | un XLSX no es texto fusionable genéricamente | merge semántico futuro |
| Kopia/restic | snapshots, objetos por contenido y recuperación independiente | no son motor de colaboración | backup posterior |

## Decisión

Se mantiene **Syncthing como transporte**. No se coloca un segundo motor
bidireccional sobre la misma carpeta.

Server Oficina añade por encima:

```text
Syncthing
  bytes / bloques / réplica / version vector
          │
          ▼
Server Oficina Sync Core
  identidad PC
  sesión humana
  eventos
  DocumentVersion
  SHA-256
  ContentStore inmutable
  FileLease
  conflicto
          │
          ▼
reconciliación semántica futura
```

## Por qué la IP no es identidad

Los peers productivos se configuran con dirección `dynamic` y Device ID. La
IP obtenida por DHCP puede cambiar. El descubrimiento local vuelve a resolver
el Device ID dentro de la LAN.

Por tanto **no se guardará 192.168.x.x como identidad de una computadora**.

El companion de Server Oficina necesitará el mismo principio para encontrar la
API web. La propuesta es DNS-SD/mDNS anunciado por Avahi, más último endpoint
válido en caché y diagnóstico de red. La UI nunca debe obligar a un usuario
normal a conocer la IP de la Latitude.

Limitación real: si un punto de acceso activa aislamiento de clientes o bloquea
broadcast/multicast/tráfico directo, dos equipos de la misma Wi-Fi pueden no
verse. No existe algoritmo local que atraviese una política que impide el
tráfico. El companion debe detectarlo y explicarlo como fallo de LAN.

## Identidad de hub migrable

La identidad del hub debe poder pasar de la Latitude a un futuro NAS/servidor.

Para Syncthing, el Device ID está ligado a su clave/certificado. El relevo
seguro podrá migrar esa identidad privada junto con Server Oficina y la BD, de
modo que las PCs sigan viendo al mismo hub lógico. Nunca deben existir dos hubs
activos con la misma clave al mismo tiempo.

El backup de esta identidad será cifrado y separado del repositorio Git.

## Identidad humana: máximo 15 días

Se separan tres conceptos:

```text
PC física          -> SyncPeer
identidad máquina  -> SyncPeerCredential
persona operando   -> WorkstationSession
```

Una sesión de estación dura como máximo 15 días por defecto. Si el turno se
extiende, la misma persona vuelve a autenticarse. Si cambia el operador antes,
se inicia sesión inmediatamente y se cierra la anterior.

Esto indica **presencia digital en la computadora**, no asistencia oficial.
RRHH sigue siendo autoridad sobre activo/descanso/incapacidad/campamento.

Los eventos offline no se tiran: al reconectar se suben con `occurred_at`.
Sólo se atribuyen a un humano cuando ese instante pertenecía a una sesión válida;
de lo contrario quedan como `DEVICE_ONLY`.

## Capas contra colisiones

### 0 · Nombre portable

Antes de indexar, se normaliza Unicode y se impiden rutas que Windows no puede
representar inequívocamente. Se detecta `Radio.xlsx` frente a `radio.xlsx`
antes de que una réplica case-insensitive tenga que decidir.

### 1 · Archivo estable

Se ignoran temporales de Office y Syncthing. Un archivo se ingiere cuando dos
observaciones muestran tamaño/mtime estables y después se verifica SHA-256.

### 2 · Lease humano

Cuando exista companion, abrir para edición pedirá un lease. Una segunda PC verá
quién edita y podrá abrir sólo lectura/esperar. Es coordinación, no un bloqueo
de filesystem absoluto.

### 3 · Conflicto de transporte

Si hubo edición offline o el lease no pudo actuar, Syncthing conserva una copia
`.sync-conflict-...`. Server Oficina la clasifica como
`CONFLICT_REVIEW`; no la deja pasar como documento normal.

### 4 · Copia histórica propia

Syncthing versiona cambios recibidos de otros peers, pero no puede versionar la
edición local anterior del mismo peer. Por eso la Latitude mantiene además un
`ContentStore` inmutable direccionado por SHA-256.

```text
versions/sha256/ab/<hash>
```

El archivo se copia a temporal, fsync, verifica SHA-256 y se promueve de forma
atómica. El tombstone de un borrado no elimina esos bytes.

### 5 · Merge semántico

Sólo para familias Excel conocidas con clave estable. BASE/LEFT/RIGHT se
comparan por registro/campo. Cambios disjuntos pueden converger; mismo campo con
valores distintos requiere humano.

### 6 · Revisión humana

Nunca se elige silenciosamente ganador por fecha para una evidencia de oficina.

## Borrado

No se habilita `ignoreDelete` como política de seguridad. La estrategia es:

1. el borrado se replica para mantener la carpeta coherente;
2. el companion registra quién/cuándo cuando puede atribuirlo;
3. `DocumentVersion` registra tombstone;
4. ContentStore conserva versiones ya observadas;
5. versionado Staggered agrega una segunda posibilidad de recuperación ante
   cambios remotos;
6. borrados masivos/anómalos deberán elevar alerta antes de cualquier purge
   histórico.

Un archivo creado y eliminado offline antes de haber llegado jamás a la
Latitude no puede ser recuperado mágicamente por el servidor. Para cubrir ese
caso el companion deberá mantener un journal local de eventos.

## Companion Windows: watcher previsto

La investigación favorece una combinación:

- `ReadDirectoryChangesW` para reacción inmediata;
- USN Journal en NTFS para recuperar el hueco después de caída/reinicio;
- cola local idempotente con `client_event_id`;
- login humano renovable cada 15 días;
- credencial de dispositivo independiente de la contraseña humana;
- lease open/heartbeat/close;
- discovery del hub sin IP fija.

No se construye un driver/minifilter en esta fase.

## Synology posterior

Las PCs nunca dependen de la estructura del Synology.

```text
PCs <-> Latitude/Hub <-> Adapter NAS <-> Synology
```

Si cambia carpeta, share, credencial o incluso marca de NAS, sólo cambia el
adapter del hub. La sincronización de las PCs continúa igual.

La réplica NAS tendrá su propio estado:

`PENDING -> .partial -> hash/tamaño -> SYNCED`.

## Gate antes de lectores/LLM

No se inicia inteligencia por área hasta cerrar:

1. unit tests Python 3.12 y 3.13;
2. tres nodos Syncthing reales en CI;
3. creación/modificación/rename/delete;
4. edición concurrente offline;
5. preservación de las dos versiones;
6. reinicio de peer/hub;
7. lote de archivos y archivo grande;
8. versión histórica independiente;
9. sesión humana y atribución offline;
10. prueba física 1 PC + Latitude;
11. 2 PCs y 5 PCs físicas;
12. cambio de Wi-Fi/DHCP;
13. Internet desconectado;
14. restore real desde historial.

## Referencias principales

- https://docs.syncthing.net/
- https://mutagen.io/documentation/synchronization
- https://github.com/bcpierce00/unison
- https://rclone.org/bisync/
- https://docs.nextcloud.com/
- https://help.seafile.com/syncing_client/file_conflicts/
- https://learn.microsoft.com/windows/win32/fileio/change-journals
- https://learn.microsoft.com/windows/win32/api/winbase/nf-winbase-readdirectorychangesw
