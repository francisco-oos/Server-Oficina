# Seguridad · 0.1.0-alpha.3

## Principios activos

- contraseñas con `scrypt` + salt aleatorio;
- sesión opaca aleatoria; en BD sólo SHA-256 del token;
- cookie `HttpOnly` + `SameSite=Lax`;
- permisos granulares por rol;
- bootstrap admin sólo si no existen usuarios;
- evidencia/importaciones con SHA-256 y nombre saneado;
- uploads de evidencia en streaming (sin cargar archivos grandes completos en RAM), escritura temporal + promoción atómica;
- indexación de archivos existentes impide escapar del repositorio mediante traversal (`..`/symlink resuelto);
- servicio `systemd` sin privilegios (`serveroficina`), `NoNewPrivileges`, `ProtectSystem`, `ProtectHome`;
- datos persistentes en `/srv/server-oficina`, fuera del código;
- Docker/containerd en `/srv/docker`;
- PostgreSQL ligado a `127.0.0.1:5432`, no a la LAN;
- secretos fuera del repo;
- UFW recomendado: 8080 sólo desde subred LAN autorizada; el instalador sólo liga la app a `0.0.0.0` cuando detecta UFW activo, de lo contrario queda en `127.0.0.1`.

## Límites de alpha

- HTTP LAN sin TLS; fuera de LAN usar VPN/HTTPS y cookie secure;
- sin MFA/SSO;
- sin rate-limit persistente de login;
- archivos sin antivirus/malware scanning todavía;
- E2E navegador físico pendiente;
- no abrir 5432 a la LAN ni 8080 a Internet;
- restore es una acción administrativa explícita, nunca automática.

## Datos humanos

La plataforma registra hechos/evidencia y no genera sanciones automáticas ni scoring laboral opaco. El acceso debe seguir mínimo privilegio y las exportaciones deben limitarse al área competente.

## Equipos/vida útil

Una observación predictiva (por ejemplo salud/RUL de NodeHealth) no autoriza retiro automático. Se conserva fuente, versión y decisión humana.
