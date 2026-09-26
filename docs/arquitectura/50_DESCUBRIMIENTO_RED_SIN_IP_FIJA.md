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
