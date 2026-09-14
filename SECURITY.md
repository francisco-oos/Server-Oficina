# Seguridad · 0.1.0-alpha.1

## Principios activos

- contraseñas con `scrypt` + salt aleatorio;
- sesión opaca aleatoria; en BD sólo se almacena SHA-256 del token;
- cookie `HttpOnly` + `SameSite=Lax`;
- permisos granulares por rol;
- primer administrador sólo cuando no existe ningún usuario;
- evidencia/importaciones con SHA-256 y nombres saneados con `Path.name`;
- proceso systemd sin privilegios (`serveroficina`) y `NoNewPrivileges=true`;
- datos persistentes fuera del código (`/var/lib/server-oficina`);
- secretos fuera del repositorio (`/etc/server-oficina/server-oficina.env`).

## Límites de alpha

- HTTP LAN sin TLS. Antes de exponer fuera de LAN debe ponerse HTTPS/VPN y activar `SERVER_OFICINA_COOKIE_SECURE=true`;
- no existe aún MFA/SSO;
- no existe todavía rate-limit persistente de login;
- archivos importados se validan por tipo/estructura, pero no existe antivirus/escaneo de malware;
- no se ha realizado todavía prueba adversarial sobre host físico;
- no abrir el puerto 8080 directamente a Internet.

## Regla de datos humanos

La plataforma documenta hechos y evidencia; no genera sanciones automáticas ni scoring laboral opaco. Permisos y resolución pertenecen al área competente.
