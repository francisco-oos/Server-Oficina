# 52 · Runbook — Gate físico 1: una PC Windows ↔ Latitude

Fecha: 2026-09-27 (actualizado para la rama de integración
`claude/syncthing-phase1-integration-v0.2`). Aplica a la candidata `0.2.0-alpha.1`.
Arquitectura y semántica: `docs/arquitectura/53_FASE_1_SINCRONIZACION_OBSERVADOR.md`. **Sólo archivos sintéticos en `LAB_SYNC`.** Ningún documento
real de RRHH, Seguridad, Transporte ni Control de Material.

Cada paso tiene un criterio de paro. Si se cumple, se detiene el gate, se
guarda evidencia y se reporta; no se improvisa sobre producción.

## 0 · Acceso

```bash
ssh adminoficina@server-oficina.local      # si mDNS resuelve
# si no: localizar la IP actual (DHCP) desde el router o en consola local:
hostname; hostname -I; ip -br a
```

La contraseña se escribe sólo en la terminal. Nunca en Git, documentos ni chat.

## 1 · PRE (sólo lectura)

```bash
cd ~/Server-Oficina                       # copia candidata
git fetch --all --prune && git checkout <rama> && git rev-parse HEAD
sudo ./scripts/evidencia-latitude.sh PRE
```

Revisar en el archivo `~/server-oficina-evidencia/PRE-*.txt`:

| Punto | Esperado | Paro si |
|---|---|---|
| `hostname` | `server-oficina` | otro nombre |
| `COLISION_RELEASE` | `NO` | `SI` |
| `/api/health` | JSON ok | falla antes de instalar (diagnosticar primero) |
| backup más reciente | `sha256sum -c` OK | SHA no verifica |
| `df -h /srv`, `/opt` | espacio para release + venv (~300 MB) | < 1 GB libre |
| VG | `serer-ficina-ADQ-vg` (typo histórico) | — **no renombrar** |
| `/srv/server-oficina/files` si ya existe | anotar dueño/modo (el instalador no los cambia; modelo esperado `root:serveroficina 2750`) | — |
| `ufw status verbose` | anotar reglas `Server Oficina LAN` fijadas a subred (se reemplazan) y la regla de SSH | SSH depende de una regla que se vaya a tocar |

## 2 · Validación del paquete en copia limpia

```bash
TMP=$(mktemp -d)
git -C ~/Server-Oficina archive HEAD | tar -x -C "$TMP"
cd "$TMP" && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
PATH="$TMP/.venv/bin:$PATH" ./VALIDAR_SERVER_OFICINA.sh     # debe terminar en PACKAGE_OK
```

`VALIDAR_SERVER_OFICINA.sh` ahora exige que el árbol coincida exactamente con
`MANIFEST.sha256` (hash distinto, archivo faltante **o archivo no listado**).

## 3 · Instalación controlada

```bash
cd ~/Server-Oficina && ./INSTALAR_EN_TABLETA.sh
```

Marcadores esperados, en orden: `Release nueva: 0.2.0-alpha.1+<fecha>.g<commit>`,
`PRE_UPGRADE_BACKUP_OK`, JSON de health, `LOCAL_CLOUD_OK` y, con UFW activo,
`LAN_FIREWALL {...}` del reconciliador.

| Salida | Significado |
|---|---|
| 4 | PostgreSQL no quedó `healthy`: no se tocó `current` |
| 5 | `/api/health` falló → `current` volvió a la release previa |
| 6 | colisión de release: no se tocó nada |
| 7 | el observador Nube Local no quedó estable → rollback completo |
| 8 | permisos de `files/` o `versions/` incompatibles con `serveroficina` |
| otra ≠ 0 antes de promover | `verify-package.sh` o `pg_dump` fallaron: `current` intacto |

Todo este flujo (incluidos los rollbacks) está probado en laboratorio con el
instalador real (`tests/integration/installer_lab.py`), **no** en la Latitude.

El instalador ya no reutiliza ni sobrescribe directorios de release: la previa
queda intacta en `/opt/server-oficina/releases/` para rollback.

## 4 · POST

```bash
sudo ./scripts/evidencia-latitude.sh POST
readlink -f /opt/server-oficina/current
curl -fsS http://127.0.0.1:8080/api/health | python3 -m json.tool
systemctl status server-oficina server-oficina-backup.timer server-oficina-local-cloud --no-pager
journalctl -u server-oficina-local-cloud -n 20 --no-pager     # LOCAL_CLOUD_START ... versions_root=/srv/server-oficina/versions
stat -c '%U:%G %a %n' /opt/server-oficina/current/ /srv/server-oficina/files /srv/server-oficina/versions
sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py status
sudo systemctl start server-oficina-backup.service && sudo cat "$(ls -1d /srv/server-oficina/backups/server-oficina/2* | tail -1)/BACKUP_INFO"
```

Esperado: código `root` sin escritura de grupo/otros; `files` `root:serveroficina 2750`
(o el modo previo anotado en PRE); `versions` `serveroficina 2750`; firewall con
la red actual confiable; `BACKUP_INFO` con `versions_replica_externa=NO_CONFIGURADA`
hasta configurar un destino externo (§ backup en doc 36).

## 5 · Syncthing del hub (LAB)

```bash
sudo ./scripts/preparar-nube-local-lab.sh            # precheck sin cambios
sudo ./scripts/preparar-nube-local-lab.sh --apply    # LAB_SYNC + syncthing@serveroficina-sync + puertos Syncthing en la LAN confiable
```

La GUI del hub sólo escucha en `127.0.0.1:8384`. Desde la PC:
`ssh -L 8384:127.0.0.1:8384 adminoficina@server-oficina.local` y abrir
`http://127.0.0.1:8384`. Definir usuario/contraseña de GUI.

Configuración (hub y PC):

- Conexiones: descubrimiento local **sí**; global **no**; relays **no**; NAT **no**.
- Dispositivo: agregar el Device ID de la otra parte con dirección `dynamic`;
  sin introducer ni auto-accept.
- Carpeta: ID `lab-sync`, etiqueta `LAB_SYNC`; en el hub la ruta es
  `/srv/server-oficina/files/LAB_SYNC`; versionado **Staggered**; ignorar
  permisos **sí**; vigilar cambios **sí**.
- Registrar versiones de Syncthing de hub y PC (Debian puede traer 1.x y la PC
  2.x; CI prueba 2.1.5).

Registrar el share en Server Oficina **después** de que exista
`/srv/server-oficina/files/LAB_SYNC/.stfolder`:

```bash
JAR=$(mktemp); chmod 600 "$JAR"
read -rp "Usuario admin: " U; read -rsp "Contraseña: " P; echo
curl -fsS -c "$JAR" -H 'Content-Type: application/json' \
  -d "$(python3 -c 'import json,sys; print(json.dumps({"username":sys.argv[1],"password":sys.argv[2]}))' "$U" "$P")" \
  http://127.0.0.1:8080/api/auth/login >/dev/null; unset P
curl -fsS -b "$JAR" -H 'Content-Type: application/json' -d '{
  "code":"LAB_SYNC","name":"Laboratorio sincronización","owner_area_code":"LAB",
  "local_root":"/srv/server-oficina/files/LAB_SYNC","syncthing_folder_id":"lab-sync"}' \
  http://127.0.0.1:8080/api/local-cloud/shares
```

El archivo `$JAR` contiene la cookie de sesión: se usa en §6 y se borra al
terminar el gate (`rm -f "$JAR"`).

`local_root` fuera de `/srv/server-oficina/files` se rechaza con 422.

Atribución técnica de **equipo** (opcional, recomendada para el gate):

1. En la GUI del hub copiar la API key (Acciones → Configuración → General).
2. Añadirla al env conservando permisos y reiniciar el observador:
   `sudo sh -c 'echo SERVER_OFICINA_SYNCTHING_API_KEY=<clave> >> /etc/server-oficina/server-oficina.env'`
   y `sudo systemctl restart server-oficina-local-cloud` (el instalador conserva
   esta clave en actualizaciones).
3. Registrar la PC con su Device ID:
   `curl -fsS -b "$JAR" -H 'Content-Type: application/json' -d '{"code":"PC-GATE1","display_name":"PC gate 1","platform":"windows","syncthing_device_id":"<DEVICE-ID-PC>"}' http://127.0.0.1:8080/api/local-cloud/peers`

Cada versión nueva tendrá `metadata.attribution` con `peer_code`, `verified` y
`person: null`: la persona y la sesión requieren Companion.

## 6 · Escenarios del gate 1

Archivos sintéticos: `Inventario_LAB.xlsx`, `Nota_LAB.docx`, `Nota_LAB.txt`,
`Binario_LAB.bin` (p. ej. 50 MB aleatorios). Registrar SHA-256 en PC
(`certutil -hashfile <archivo> SHA256`) y hub (`sha256sum`).

Consulta de historial:

```bash
curl -fsS -b "$JAR" http://127.0.0.1:8080/api/local-cloud/documents | python3 -m json.tool
curl -fsS -b "$JAR" http://127.0.0.1:8080/api/local-cloud/documents/<id>/versions | python3 -m json.tool
```

| # | Acción en la PC | Esperado en hub / Server Oficina |
|---|---|---|
| 1 | crear | mismo SHA; versión `MODIFIED`; objeto en `versions/sha256/..` |
| 2 | modificar | segunda versión; la primera sigue verificable |
| 3 | renombrar | `DELETED` en el nombre viejo + documento nuevo con el mismo SHA |
| 4 | mover a subcarpeta | igual que renombrar |
| 5 | borrar | tombstone `DELETED`; bytes siguen en ContentStore y `.stversions` |
| 6 | restaurar desde Papelera | versión `RECOVERED`; documento vivo |
| 7 | reiniciar PC | converge sin intervención |
| 8 | reiniciar Latitude | servicios arriba solos; converge |
| 9 | cortar red de la PC, editar, reconectar | converge; sin pérdida |
| 10 | apagar Internet (LAN arriba) | todo lo anterior sigue funcionando |

| 11 | archivo sintético con nombre no válido en Windows creado en el hub | incidencia `NAME_NOT_PORTABLE` en `metadata.observer`; el resto sigue |
| 12 | detener `syncthing@serveroficina-sync` y mover `LAB_SYNC` (simula disco ausente) | observador `UNAVAILABLE` (`ROOT_MISSING`/`SYNCTHING_MARKER_MISSING`), **0** versiones `DELETED`; al restaurar, `AVAILABLE` sin pérdidas |

Evidencia de cada versión: `metadata.attribution.peer_code` = PC del gate y
`verified: true` si se configuró la API key; sin ella `source_peer_id` queda
vacío (correcto: no se inventa atribución). Persona/sesión: **no aplica** hasta
Companion.

Al terminar: `sudo ./scripts/verificar-historial.sh --deep` debe imprimir `HISTORY_OK`.

## 7 · Cambio de Wi-Fi / DHCP

Registrar IP anterior, IP nueva, tiempo hasta reconexión Syncthing y hasta
`/api/health` desde la PC. **No** editar Device IDs.

El firewall ya no fija la subred de la instalación: `server-oficina-lan-firewall`
confía por **red** (SSID o cable) y recalcula la subred en cada cambio
(dispatcher de NetworkManager o timer cada 2 min).

| Caso | Esperado | Intervención permitida |
|---|---|---|
| misma Wi-Fi, nueva IP por DHCP | reconecta solo | ninguna |
| misma Wi-Fi (SSID), router nuevo con otra subred | reglas recalculadas ≤ 2 min | ninguna |
| Wi-Fi distinta (otro SSID) | **sin** reglas LAN hasta decidirlo | `sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py trust-current` (decisión de confianza, no edición de IP) |
| red pública / no RFC1918 | nunca se abre | — |

Si hizo falta editar una IP o una subred a mano, el gate **falla**. Registrar
`lan_firewall.py status` antes y después del cambio y el tiempo de recuperación.
Debe verificarse también que el reconciliador **no** tocó la regla de SSH.

## 8 · Criterio para pasar al gate de 2 PCs

Todos los escenarios de §6 y §7 con evidencia (SHA, logs, tiempos), ningún
reinicio del observador (`NRestarts=0`), `verify_history --deep` en
`HISTORY_OK`, backup diario verificado con `BACKUP_INFO`, restore probado a base
temporal y decisión tomada sobre la réplica externa de `versions/`.
