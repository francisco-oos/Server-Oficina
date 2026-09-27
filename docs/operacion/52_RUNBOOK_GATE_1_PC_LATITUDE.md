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
| `ufw status verbose` | activo, `Default: deny (incoming)`; anotar reglas `Server Oficina LAN` fijadas a subred (se reemplazan) y la regla de SSH | SSH depende de una regla que se vaya a tocar |
| `ip -br addr`, `ip -4 route show default` | una línea por interfaz activa: Ethernet (`enp…`) y Wi-Fi (`wlp…`) pueden estar **las dos**, cada una con su IPv4 y su ruta por defecto (métricas distintas) | una interfaz está en una red que no es de la oficina y se pretende confiar en ella |
| por **cada** interfaz: `ip neigh show <gateway> dev <if>`, SSID (`iw dev <wlp…> link`), `nmcli -t -f DEVICE,UUID,NAME connection show --active` | anotar interfaz, subred, gateway, MAC del gateway, SSID y perfil NM: es la identidad de **esa** LAN | — |
| `lan_firewall.py audit` (sección "Descubrimiento local y no-enrutamiento" de la evidencia) | Avahi activo sin reflector ni interfaces excluidas; `ip_forward=0`, o `1` por Docker con `FORWARD DROP` | `enable-reflector=yes`, `FORWARD ACCEPT` con `ip_forward=1`, NAT de una LAN |

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
# Ethernet y Wi-Fi activas, ambas LAN de la oficina verificadas en PRE:
cd ~/Server-Oficina && ./INSTALAR_EN_TABLETA.sh --confiar-interfaz <enp…> --confiar-interfaz <wlp…>
# Una sola LAN activa:
cd ~/Server-Oficina && ./INSTALAR_EN_TABLETA.sh --confiar-red-actual
```

Confiar es una decisión explícita **por LAN**: cada `--confiar-interfaz` guarda
la identidad de la LAN de esa interfaz (MAC del gateway + perfil NM + SSID), no
el nombre de la interfaz. `--confiar-red-actual` sólo actúa si hay exactamente
una LAN activa; con dos se niega (nunca se confía una LAN por estar enchufada).
Sin ninguna LAN confiable la API queda sólo en `127.0.0.1` (salida 10).

Marcadores esperados, en orden: `Release nueva: 0.2.0-alpha.1+<fecha>.g<commit>`,
`PRE_UPGRADE_BACKUP_OK`, JSON de health, `LOCAL_CLOUD_OK`, `LAN_FIREWALL {...}`
del reconciliador y `LAN_PUBLICADA` con una línea por LAN publicada
(`<if> (wired|wifi): http://<IP de esa LAN>:8080  LAN <subred>`).

| Salida | Significado |
|---|---|
| 4 | PostgreSQL no quedó `healthy`: no se tocó `current` |
| 5 | `/api/health` falló → `current` volvió a la release previa |
| 6 | colisión de release: no se tocó nada |
| 7 | el observador Nube Local no quedó estable → rollback completo |
| 8 | permisos de `files/` o `versions/` incompatibles con `serveroficina` |
| 10 | `INSTALACION_SOLO_LOCAL`: release instalada y sana en `127.0.0.1`, pero la LAN **no** se publicó (`LAN_NO_PUBLICADA: <causa>`). No es un gate PASS: corregir la causa y ejecutar `sudo /opt/server-oficina/current/scripts/configurar-acceso-lan.sh [--confiar-red-actual]` |
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
grep '^SERVER_OFICINA_HOST=' /etc/server-oficina/server-oficina.env       # 0.0.0.0 sólo con LAN_PUBLICADA
sudo ss -ltnp 'sport = :8080'                                              # escucha coherente con lo anterior
sudo ufw status numbered | grep -E 'server-oficina-lan|22/tcp|SSH'         # reglas "on <if>" por cada LAN confiable; SSH intacta
sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py audit    # LAN_AUDIT con "problemas": []
sudo systemctl start server-oficina-backup.service && sudo cat "$(ls -1d /srv/server-oficina/backups/server-oficina/2* | tail -1)/BACKUP_INFO"
```

Esperado: código `root` sin escritura de grupo/otros; `files` `root:serveroficina 2750`
(o el modo previo anotado en PRE); `versions` `serveroficina 2750`; firewall con
cada LAN de la oficina confiable (`published` lista las dos interfaces si ambas
están activas); `BACKUP_INFO` con `versions_replica_externa=NO_CONFIGURADA`
hasta configurar un destino externo (§ backup en doc 36).

## 5 · Syncthing del hub (LAB)

```bash
sudo ./scripts/preparar-nube-local-lab.sh            # precheck sin cambios
sudo ./scripts/preparar-nube-local-lab.sh --apply    # LAB_SYNC + syncthing@serveroficina-sync + puertos Syncthing en la LAN confiable
```

`--apply` habilita 22000/tcp, 22000/udp y 21027/udp en **cada** LAN confiable
activa. Para el nombre local: `sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py enable mdns`
(5353/udp por LAN; ver §7.2 sobre el mDNS multicast que UFW ya admite).

La GUI del hub sólo escucha en `127.0.0.1:8384`. Desde la PC:
`ssh -L 8384:127.0.0.1:8384 adminoficina@server-oficina.local` y abrir
`http://127.0.0.1:8384`. Definir usuario/contraseña de GUI.

Configuración (hub y PC):

- Conexiones: descubrimiento local **sí**; global **no**; relays **no**; NAT **no**.
- Direcciones de escucha del hub: `default` (tcp y quic en `0.0.0.0:22000`):
  escucha en Ethernet y Wi-Fi a la vez. No fijar una IP concreta. El
  descubrimiento local anuncia por broadcast en cada interfaz; la PC aprende la
  IP del hub **de su propia LAN**.
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

## 7 · Acceso por Ethernet, por Wi-Fi y por ambas a la vez

La Latitude puede estar conectada **simultáneamente** por Ethernet (LAN A) y por
Wi-Fi (LAN B). Server Oficina debe poder encontrarse y usarse desde cualquiera
de las dos, y la Latitude **no** debe enrutar entre ellas (sin forwarding,
bridge ni NAT): sólo ofrece sus propios servicios en cada interfaz.

```
LAN A ─── Ethernet ─┐
                    Latitude          (no: LAN A ← router → LAN B)
LAN B ───── Wi-Fi ──┘
```

Sigue siendo el Gate 1: **una** PC, que se conecta primero por cable y después
por Wi-Fi. Si hay otro equipo a mano sólo se usa como sonda (resolver, HTTP),
nunca como segunda PC de producción. Todo con archivos sintéticos en `LAB_SYNC`.

### 7.1 · Comprobaciones en la Latitude (repetir en cada paso)

```bash
ip -br addr; ip -4 route show default                  # ambas interfaces y ambas rutas por defecto
sudo ufw status numbered                                # reglas "on <enp…>" y "on <wlp…>", cada una con su subred
sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py status   # published, estado por LAN, api
sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py audit    # "problemas": []
journalctl -u avahi-daemon -n 20 --no-pager             # "Registering new address record for <IP> on <if>.IPv4" por interfaz
sudo ss -tulpn | grep -E ':(8080|22000|21027|5353)\b'   # 8080 y 22000 en 0.0.0.0/*: escuchan en ambas
```

Reglas esperadas con ambas LAN confiables y Syncthing + mDNS habilitados
(salida real del laboratorio `multi_lan_lab.py`; en la Latitude cambian los
nombres de interfaz y las subredes):

```
[ 1] 22/tcp                     ALLOW IN    Anywhere                   # ssh
[ 2] 8080/tcp on enp0s31f6      ALLOW IN    192.168.10.0/24            # server-oficina-lan
[ 3] 8080/tcp on wlp2s0         ALLOW IN    192.168.48.0/24            # server-oficina-lan
[ 4] 21027/udp on enp0s31f6     ALLOW IN    192.168.10.0/24            # server-oficina-lan
[ 5] 22000/tcp on enp0s31f6     ALLOW IN    192.168.10.0/24            # server-oficina-lan
[ 6] 22000/udp on enp0s31f6     ALLOW IN    192.168.10.0/24            # server-oficina-lan
[ 7] 21027/udp on wlp2s0        ALLOW IN    192.168.48.0/24            # server-oficina-lan
[ 8] 22000/tcp on wlp2s0        ALLOW IN    192.168.48.0/24            # server-oficina-lan
[ 9] 22000/udp on wlp2s0        ALLOW IN    192.168.48.0/24            # server-oficina-lan
[10] 5353/udp on enp0s31f6      ALLOW IN    192.168.10.0/24            # server-oficina-lan
[11] 5353/udp on wlp2s0         ALLOW IN    192.168.48.0/24            # server-oficina-lan
```

Nunca debe aparecer una regla propia con `Anywhere`, ni una regla de una
interfaz con la subred de la otra.

### 7.2 · Comprobaciones desde la PC (Windows, PowerShell)

```powershell
ping -4 server-oficina.local                       # muestra la IP resuelta: la de la Latitude EN LA LAN DE LA PC
Resolve-DnsName server-oficina.local -Type A       # opcional: según la versión de Windows puede no consultar mDNS
curl.exe -fsS http://server-oficina.local:8080/api/health
Test-NetConnection server-oficina.local -Port 22000
ssh adminoficina@server-oficina.local "hostname; ip -br addr"
```

Si la PC no resuelve `.local` (resolvedor de Windows sin mDNS), se anota como
hallazgo de la PC —no de la Latitude—, se verifica el anuncio desde otro equipo
de esa LAN si lo hay, y el resto del paso se hace con la IP de esa LAN.

`server-oficina.local` lo anuncia Avahi con el hostname del sistema en cada
interfaz, y cada interfaz responde con **su** dirección: por cable debe resolver
a la IP Ethernet de la Latitude y por Wi-Fi a la IP Wi-Fi. mDNS es link-local:
no se enruta ni se refleja entre LAN (`enable-reflector` debe seguir en `no`).
UFW de Debian ya admite el mDNS multicast (`224.0.0.251:5353`) en su
`before.rules`; las reglas 5353 propias limitan además el mDNS unicast a cada
LAN confiable. Consecuencia conocida: en una LAN **no** confiable directamente
conectada, la Latitude también responde a `server-oficina.local` (nombre e IP,
que esa red ya conoce por DHCP), pero 8080 y 22000 siguen cerrados ahí.

### 7.3 · Pasos

| # | Situación | Esperado | Paro si |
|---|---|---|---|
| 1 | PC **por cable** a la LAN A (Wi-Fi de la PC apagada); Latitude con ambas | resuelve a la IP Ethernet; HTTP, SSH y Syncthing OK; en la GUI de Syncthing de la PC, dirección del hub = IP Ethernet | resuelve a la IP Wi-Fi o a `server-oficina-2.local` |
| 2 | PC **por Wi-Fi** a la LAN B (cable de la PC desconectado) | resuelve a la IP Wi-Fi; HTTP, SSH y Syncthing OK; dirección del hub = IP Wi-Fi | resuelve a la IP Ethernet |
| 3 | Latitude con **ambas** activas: repetir 1 y 2 sin tocar la Latitude | los dos accesos funcionan; `status` publica las dos LAN; 10 reglas (con Syncthing y mDNS) | hace falta desconectar una interfaz para que la otra funcione |
| 4 | desconectar el **cable de la Latitude**, PC por Wi-Fi | la Wi-Fi sigue sin corte (HTTP en bucle, Syncthing conectado); en ≤ 2 min (al momento con el dispatcher) sólo quedan reglas `on <wlp…>`; `api.actual` sigue `0.0.0.0` | se corta la Wi-Fi o se reinicia la API |
| 5 | reconectar el cable, PC por cable | vuelven las reglas `on <enp…>` sin nueva confianza; acceso por cable OK | pide volver a confiar |
| 6 | apagar la **Wi-Fi de la Latitude** (`nmcli radio wifi off`), PC por cable | igual que 4 al revés | se corta Ethernet |
| 7 | encender la Wi-Fi | vuelve la LAN B; acceso por Wi-Fi OK | — |
| 8 | (si es posible) cable de la Latitude a una LAN **ajena** | `status`: `<enp…>` `no_confiable`, sin reglas; la Wi-Fi sigue publicada | se publica la LAN ajena |
| 9 | desconectar ambas | `api.actual` pasa a `127.0.0.1` (`ss` muestra `127.0.0.1:8080`); al volver cualquiera confiable, `0.0.0.0` | la API queda en `0.0.0.0` sin LAN confiable |
| 10 | no-enrutamiento: en la PC por cable, `route add <subred LAN B> mask <máscara> <IP Ethernet de la Latitude>` y probar un equipo de la LAN B | **falla**; `sysctl net.ipv4.ip_forward` = 0 (o 1 por Docker con `iptables -S FORWARD` → `-P FORWARD DROP`) | cruza a la otra LAN |

Tras el paso 10, borrar la ruta de prueba en la PC (`route delete <subred LAN B>`).

### 7.4 · Cambio de red / DHCP (por cada LAN, de forma independiente)

Registrar IP anterior, IP nueva, tiempo hasta reconexión Syncthing y hasta
`/api/health` desde la PC. **No** editar Device IDs.

El firewall confía por **identidad de red** de cada LAN (MAC del gateway +
perfil NetworkManager + SSID; nunca sólo el SSID o el nombre de la interfaz) y
recalcula la subred de cada una en cada cambio (dispatcher de NetworkManager
en `up`/`down`/`dhcp4-change`, o timer cada 2 min). Un cambio en una LAN no
toca las reglas de la otra.

| Caso (en cualquiera de las dos LAN) | Esperado | Intervención permitida |
|---|---|---|
| misma red, nueva IP por DHCP | reconecta solo | ninguna |
| mismo router, rango DHCP cambiado | reglas de esa LAN recalculadas ≤ 2 min; la otra intacta | ninguna |
| mismo SSID en otro router (p. ej. punto de acceso móvil con el mismo nombre) | **sin** reglas para esa LAN | ninguna (correcto) |
| router de esa LAN reemplazado | **sin** reglas para esa LAN hasta decidirlo; la otra sigue | `sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py trust-current --interface <if>` |
| Wi-Fi distinta | **sin** reglas Wi-Fi hasta decidirlo | ídem con la interfaz Wi-Fi |
| red pública / no RFC1918 | nunca se abre | — |

Si hizo falta editar una IP o una subred a mano, el gate **falla**. Registrar
`lan_firewall.py status` antes y después de cada cambio y el tiempo de
recuperación. Verificar también que el reconciliador **no** tocó la regla de SSH.

## 8 · Criterio para pasar al gate de 2 PCs

Todos los escenarios de §6 y §7 con evidencia (SHA, logs, tiempos), incluidos
los dos accesos (Ethernet y Wi-Fi), ambos a la vez y la pérdida/recuperación
independiente de cada interfaz; ningún
reinicio del observador (`NRestarts=0`), `verify_history --deep` en
`HISTORY_OK`, backup diario verificado con `BACKUP_INFO`, restore ejecutado con
`RESTORE_SERVER_OFICINA.sh` (resultado `RESTORE_OK` en
`/srv/server-oficina/backups/restore-logs/`, base previa
`server_oficina_pre_restore_*` revisada y borrada a mano) y decisión tomada
sobre la réplica externa de `versions/`.
