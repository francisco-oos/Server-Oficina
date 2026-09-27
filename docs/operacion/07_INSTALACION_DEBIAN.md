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
12. publica 8080 en la LAN **sólo si puede demostrarlo** (ver «Acceso LAN»);
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

## Acceso LAN (fail-closed)

`SERVER_OFICINA_HOST` vale `127.0.0.1` salvo que `configurar-acceso-lan.sh`
(el instalador lo ejecuta si UFW está activo) demuestre, en este orden:

1. UFW activo con política entrante por defecto `deny`/`reject`;
2. la red actual es **confiable** (ver identidad abajo);
3. las reglas gestionadas quedaron aplicadas y verificadas
   (`lan_firewall.py apply --require-rules`);
4. `/api/health` responde tras escuchar en `0.0.0.0`.

Sólo entonces imprime `LAN_PUBLICADA`. Cualquier fallo (incluido un error
inesperado) deja la API en `127.0.0.1`, imprime `LAN_NO_PUBLICADA: <causa>` y
sale con 10; el instalador propaga `INSTALACION_SOLO_LOCAL` (salida 10). Nunca
desactiva UFW, nunca abre 8080 a cualquier origen y nunca toca reglas ajenas
(SSH). Sin UFW activo la instalación es local por diseño (salida 0, API en
`127.0.0.1`).

La primera vez, la red actual no es confiable: confiar es una decisión explícita
del operador, tras comprobar que está en la red de la oficina:

```bash
./INSTALAR_EN_TABLETA.sh --confiar-red-actual                         # instalar y confiar en esta red
sudo /opt/server-oficina/current/scripts/configurar-acceso-lan.sh --confiar-red-actual   # o después
```

### Identidad de red

Ni el SSID ni el nombre de la interfaz identifican una red (otra Wi-Fi puede
llamarse igual; `eth0` puede enchufarse a otra LAN). La identidad guardada al
confiar es: **MAC del gateway** (obligatoria) + **UUID del perfil de
NetworkManager** (si gestiona la interfaz) + **SSID** (Wi-Fi) + medio. Una red
es confiable sólo si todos coinciden.

| Situación | Resultado |
|---|---|
| misma red, nueva IP por DHCP | sin intervención |
| mismo router, otro rango DHCP | reglas siguen la subred nueva (≤ 2 min) |
| mismo SSID en otro router / misma `eth0` en otra LAN | **no** confiable: sin reglas |
| router reemplazado en la oficina | exige `trust-current` (compromiso asumido) |
| identidad ilegible un momento (ARP vacío, NM reiniciando) | reglas mantenidas ≤ 10 min si interfaz, subred y gateway no cambian; luego se cierran |
| red pública / no RFC1918 | nunca se abre |

```bash
sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py status          # qué corresponde y por qué
sudo python3 /opt/server-oficina/current/scripts/lan_firewall.py trust-current   # confiar en la red actual
```

Las confianzas antiguas (`wifi:<SSID>`, `wired:<iface>`) se ignoran: hay que
volver a confiar una vez. Las reglas antiguas fijadas a una subred
(`Server Oficina LAN`) se reemplazan.

Riesgo residual: una vez publicada, la protección de 8080 es UFW. Si alguien
ejecuta `ufw disable` a mano, la API queda accesible; `lan_firewall.py status`
lo muestra (`"ufw": "inactivo…"`) y basta ejecutar `configurar-acceso-lan.sh`
para volver a `127.0.0.1`.

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
