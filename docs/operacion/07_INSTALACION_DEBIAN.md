# 07 · Instalación Debian / Latitude — alpha.2

## Importante

Esta guía sustituye el instalador alpha.1. **No instale PostgreSQL nativo** ni use `/var/lib/server-oficina` en la Latitude preparada.

## Precondiciones verificadas

- Debian 13 Trixie amd64;
- SSH;
- UFW;
- Docker Engine + Compose;
- `/srv/server-oficina`;
- `/srv/docker`;
- PostgreSQL 18.6 probado con persistencia y restore.

## Instalar release

```bash
chmod +x *.sh scripts/*.sh
./VALIDAR_SERVER_OFICINA.sh
./INSTALAR_EN_TABLETA.sh
```

El instalador:

1. conserva/genera el secreto PostgreSQL en `/srv/server-oficina/secrets/postgres_password`;
2. instala el compose canónico en `/srv/server-oficina/app/infra/compose.yml`;
3. levanta PostgreSQL 18.6 con datos en `/srv/server-oficina/data/postgres`;
4. publica PostgreSQL sólo en `127.0.0.1:5432`;
5. instala la release en `/opt/server-oficina/releases/<VERSION>`;
6. crea `.venv` por release;
7. actualiza `/opt/server-oficina/current`;
8. genera `/etc/server-oficina/server-oficina.env`;
9. instala/arranca `server-oficina.service`;
10. instala backup timer;
11. prueba `/api/health`;
12. publica 8080 en cada LAN confiable **sólo si puede demostrarlo** (ver «Acceso LAN»);
    si no, la API queda en `127.0.0.1` y la instalación sale con código 10
    (`INSTALACION_SOLO_LOCAL`), nunca declarada sana con la API expuesta.

## Estado

```bash
./ESTADO_SERVER_OFICINA.sh
```

## Abrir localmente

```bash
./ABRIR_SERVER_OFICINA.sh
```

Desde otro equipo autorizado use `http://IP_DE_LA_TABLET:8080`.

## Acceso LAN (fail-closed, Ethernet + Wi-Fi)

La Latitude puede estar conectada **a la vez** por Ethernet y por Wi-Fi, cada
interfaz a una LAN de la oficina. Server Oficina se ofrece en **todas** las LAN
confiables activas simultáneamente; la Latitude no enruta entre ellas (sin
forwarding, bridge ni NAT: sólo ofrece sus propios servicios en cada interfaz).

`SERVER_OFICINA_HOST` vale `127.0.0.1` salvo que `configurar-acceso-lan.sh`
(el instalador lo ejecuta si UFW está activo) demuestre, en este orden:

1. UFW activo con política entrante por defecto `deny`/`reject`;
2. al menos una LAN activa es **confiable** (ver identidad abajo);
3. las reglas gestionadas quedaron aplicadas y verificadas
   (`lan_firewall.py apply --require-rules`);
4. `/api/health` responde tras escuchar en `0.0.0.0`.

Sólo entonces imprime `LAN_PUBLICADA`, con una línea por LAN publicada. Cualquier
fallo (incluido un error inesperado) deja la API en `127.0.0.1`, imprime
`LAN_NO_PUBLICADA: <causa>` y sale con 10; el instalador propaga
`INSTALACION_SOLO_LOCAL` (salida 10). Nunca desactiva UFW, nunca abre 8080 a
cualquier origen y nunca toca reglas ajenas (SSH). Sin UFW activo la instalación
es local por diseño (salida 0, API en `127.0.0.1`).

Después, `server-oficina-lan-firewall` (timer cada 2 min y dispatcher de
NetworkManager en `up`/`down`/`dhcp4-change`) mantiene el invariante: un único
listener `0.0.0.0:8080` mientras quede al menos una LAN confiable con reglas
verificadas y UFW protegiendo; `127.0.0.1` si no queda ninguna (o si UFW deja de
estar activo con entrada `deny`). La API sólo se reinicia al cruzar entre
"ninguna LAN" y "alguna LAN"; que caiga una de dos LAN no la reinicia.

Confiar es una decisión explícita del operador **por LAN**, tras comprobar que
cada una es de la oficina:

```bash
./INSTALAR_EN_TABLETA.sh --confiar-interfaz <enp…> --confiar-interfaz <wlp…>   # Ethernet y Wi-Fi
./INSTALAR_EN_TABLETA.sh --confiar-red-actual          # sólo si hay exactamente una LAN activa
sudo /opt/server-oficina/current/scripts/configurar-acceso-lan.sh --confiar-interfaz <if>   # o después
```

Con dos LAN activas, `--confiar-red-actual` se niega: nunca se confía una LAN
por el hecho de estar enchufada al mismo tiempo que otra.

### Interfaces que cuentan

NIC físicas Ethernet o Wi-Fi (`/sys/class/net/<if>/device`; Wi-Fi si tiene
`wireless`), en estado `up`, con IPv4 global y no esclavas de un bridge. El
nombre no importa (`enp…`, `wlp…`, `enx…` de un adaptador USB, `eth0`…). Docker,
bridges, veth, VPN y túneles nunca se publican.

### Identidad de red (por LAN)

Ni el SSID ni el nombre de la interfaz identifican una red (otra Wi-Fi puede
llamarse igual; un cable puede enchufarse a otra LAN). La identidad guardada al
confiar cada LAN es: **MAC del gateway de esa interfaz** (obligatoria) +
**UUID del perfil de NetworkManager** (si gestiona la interfaz) + **SSID**
(Wi-Fi) + medio. Una LAN es confiable sólo si todos coinciden. Se guardan todas
las LAN confiadas a la vez (`trusted_networks` en `/etc/server-oficina/lan-firewall.json`):

```json
{"trusted_networks": [
  {"id": "medium=wired|gw_mac=aa:bb:cc:00:00:0a",
   "components": {"medium": "wired", "gw_mac": "aa:bb:cc:00:00:0a", "nm": "<uuid perfil cable>"},
   "first_iface": "enp0s31f6", "first_subnet": "192.168.10.0/24"},
  {"id": "medium=wifi|ssid=Oficina|gw_mac=aa:bb:cc:00:00:0b",
   "components": {"medium": "wifi", "ssid": "Oficina", "gw_mac": "aa:bb:cc:00:00:0b", "nm": "<uuid perfil wifi>"},
   "first_iface": "wlp2s0", "first_subnet": "192.168.48.0/24"}]}
```

`first_iface`/`first_subnet` son informativos; la subred actual de cada LAN se
lee en cada ejecución y el estado por interfaz queda en
`/var/lib/server-oficina/lan-firewall-state.json`.

| Situación (en cualquiera de las LAN) | Resultado |
|---|---|
| misma red, nueva IP por DHCP | sin intervención |
| mismo router, otro rango DHCP | reglas de esa LAN siguen la subred nueva (≤ 2 min); la otra no se toca |
| mismo SSID en otro router / mismo cable en otra LAN | **no** confiable: sin reglas para esa LAN; la otra sigue |
| router reemplazado en la oficina | exige `trust-current --interface <if>` (compromiso asumido) |
| identidad ilegible un momento (ARP vacío, NM reiniciando) | reglas de esa interfaz mantenidas ≤ 10 min si su subred y gateway no cambian; luego se cierran |
| interfaz caída (cable fuera, Wi-Fi apagada) | se retiran sólo sus reglas; la otra LAN sigue publicada |
| LAN sin gateway | sin identidad verificable: no se publica (limitación conocida) |
| red pública / no RFC1918 | nunca se abre |

```bash
sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py status                      # estado por LAN y por qué
sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py trust-current --interface <if>
sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py audit                       # mDNS, Syncthing, no-enrutamiento
```

Las confianzas antiguas (`wifi:<SSID>`, `wired:<iface>`) se ignoran: hay que
volver a confiar una vez. Las reglas antiguas fijadas a una subred
(`Server Oficina LAN`) se reemplazan.

### Descubrimiento: `server-oficina.local`

Avahi anuncia el hostname del sistema (`server-oficina`) en cada interfaz, y
cada interfaz responde con **su** dirección: una PC por cable resuelve la IP
Ethernet de la Latitude y una por Wi-Fi la IP Wi-Fi. No hace falta reflector ni
reenvío de multicast: mDNS es link-local y la Latitude está directamente en
ambas LAN (`enable-reflector` debe seguir en `no`; `audit` lo comprueba).
Syncthing escucha en `0.0.0.0:22000` (tcp y quic) y el descubrimiento local
anuncia por cada interfaz: cada PC aprende la IP del hub de su propia LAN.

UFW de Debian (0.36.2) acepta en su `before.rules` el mDNS multicast
(`224.0.0.251:5353`) desde cualquier interfaz; no se modifica. Las reglas 5353
propias (`lan_firewall.py enable mdns`) limitan además el mDNS unicast a cada
LAN confiable. Consecuencia: en una LAN no confiable directamente conectada la
Latitude también responde a `server-oficina.local` (nombre e IP, que esa red ya
ve por DHCP), pero 8080 y 22000 siguen cerrados allí.

Riesgo residual: una vez publicada, la protección de 8080 es UFW. Si alguien
ejecuta `ufw disable` a mano, el reconciliador vuelve la API a `127.0.0.1` en su
siguiente ejecución (≤ 2 min).

## Backup / Restore

```bash
./BACKUP_SERVER_OFICINA.sh
./RESTORE_SERVER_OFICINA.sh /srv/server-oficina/backups/server-oficina/AAAAMMDD-HHMMSS
```

El restore valida el respaldo entero, restaura en una base temporal en una sola
transacción e intercambia de forma atómica; si algo falla, la base viva no se
toca o se revierte (códigos y garantías en `36_BACKUP_RESTORE.md`). Aun así, no
ejecute restore sobre datos reales sin confirmar el backup objetivo y una
ventana de mantenimiento.
