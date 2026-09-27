# 50 · Arquitectura — descubrimiento local sin IP fija

Fecha: 2026-09-26.

## Objetivo

Cambiar de router, SSID o rango DHCP no debe obligar a reconfigurar cada PC.
La IP es una dirección efímera, no la identidad de una computadora ni del hub.

## Plano de sincronización

Syncthing identifica dispositivos mediante Device ID derivado de su clave y
puede resolver direcciones dinámicas mediante descubrimiento local. En la
configuración de Server Oficina:

- dirección de peers: `dynamic`;
- descubrimiento local: habilitado;
- descubrimiento global: deshabilitado;
- relays: deshabilitados;
- NAT traversal: deshabilitado.

Así el transporte sigue siendo LAN-only y la reasignación DHCP no cambia la
identidad del dispositivo.

## Plano de API Server Oficina

El Companion no debe guardar `http://192.168.x.x:8080` como identidad.

Se adopta DNS-SD/mDNS para anunciar un servicio lógico:

```text
_server-oficina._tcp.local
  instance = Server Oficina
  host     = server-oficina.local
  port     = 8080
```

En Debian, Avahi puede publicar ese servicio. El Companion busca instancias,
prueba `/api/health` y valida la identidad emparejada del servidor antes de
usar el endpoint.

El registro mDNS no contiene contraseñas, tokens, rutas sensibles ni secretos.

## Latitude en dos LAN a la vez (Ethernet + Wi-Fi)

Actualizado 2026-09-27. El hub puede estar conectado simultáneamente por cable a
una LAN y por Wi-Fi a otra. Requisito: las PCs de **cualquiera** de las dos lo
encuentran y lo usan; las PCs de una LAN no necesitan alcanzar a las de la otra.

- **Nombre:** Avahi publica `server-oficina.local` (hostname del sistema) en
  cada interfaz, y cada interfaz responde con **su** dirección: una PC por
  cable obtiene la IP Ethernet de la Latitude; una por Wi-Fi, la IP Wi-Fi.
  Verificado con Avahi 0.8 real en `tests/integration/multi_lan_lab.py`
  ("Registering new address record for <IP> on <if>.IPv4" por interfaz).
- **Sin reflector ni reenvío:** mDNS es link-local y la Latitude pertenece
  directamente a ambas LAN; `enable-reflector` debe seguir en `no` y no hay
  forwarding, bridge ni NAT entre ellas (`lan_firewall.py audit`).
- **Syncthing:** escucha en `0.0.0.0:22000` (tcp y quic) y el descubrimiento
  local anuncia por broadcast en cada interfaz; cada PC aprende la IP del hub de
  su propia LAN. Con una interfaz caída, la otra sigue sin reconectar.
- **Firewall:** reglas por LAN confiable (`in on <if> from <subred>`), ver doc
  53 §9 y doc 07.
- **Mismo hostname en ambas LAN:** si Avahi informa un conflicto y renombra a
  `server-oficina-2.local`, es un hallazgo del gate físico (runbook 52 §7).

## Orden de resolución del Companion

1. sesión/conexión actual si continúa sana;
2. DNS-SD/mDNS en la interfaz LAN activa;
3. último endpoint observado como fallback rápido;
4. diagnóstico explícito si no hay conectividad local.

El endpoint encontrado es dirección; la confianza viene del emparejamiento y
de la identidad del servidor, no del nombre `.local` por sí solo.

## Cambio de Wi-Fi

Si las PCs y el hub vuelven a estar en una LAN que permite comunicación entre
clientes, el descubrimiento se repite y recupera la nueva dirección.

Limitación física: algunos APs habilitan client isolation o filtran
broadcast/multicast. Syncthing documenta que el descubrimiento local requiere
que el router permita esos paquetes; mDNS también es link-local. Server Oficina
no intentará ocultar esta condición. El Companion mostrará un diagnóstico tipo:

> Red disponible, pero comunicación LAN/descubrimiento local bloqueados.

Si en el futuro la oficina usa VLANs/subredes separadas, la solución correcta
será DNS unicast interno o un reflector mDNS administrado, no escaneo agresivo
de rangos ni depender de Internet.

## Migración futura del hub

La Latitude es el primer host. Un futuro NAS/servidor puede asumir el rol si
migra de manera gobernada:

- base y configuración de Server Oficina;
- identidad de aplicación;
- identidad Syncthing si se decide conservar el mismo Device ID;
- ContentStore/manifest y ubicaciones verificadas.

Nunca deben operar simultáneamente dos hosts usando la misma clave privada de
identidad.

## Pruebas de aceptación

- Latitude con Ethernet y Wi-Fi activas: resolver `server-oficina.local` desde
  una PC por cable y por Wi-Fi (cada una obtiene la IP de su LAN);
- caída y regreso independiente de cada interfaz;
- cambiar DHCP manteniendo la misma red;
- cambiar a otro router/SSID LAN;
- reiniciar hub y cliente;
- desactivar Internet manteniendo LAN;
- bloquear mDNS y comprobar diagnóstico;
- comprobar que ningún secreto aparece en anuncios DNS-SD;
- comprobar que un servicio impostor no supera el emparejamiento.

## Referencias

- RFC 6762 — Multicast DNS: https://www.rfc-editor.org/rfc/rfc6762
- RFC 6763 — DNS-Based Service Discovery: https://www.rfc-editor.org/rfc/rfc6763
- Avahi publish service: https://manpages.debian.org/trixie/avahi-utils/avahi-publish-service.1.en.html
- Syncthing Device IDs: https://docs.syncthing.net/users/device-ids.html
- Syncthing networking/local discovery: https://docs.syncthing.net/users/firewall.html
