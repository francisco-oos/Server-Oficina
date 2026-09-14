# Seguridad · 0.1.0-alpha.4

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
- la configuración del dashboard **acota pero nunca amplía** privilegios: el permiso
  declarado por cada widget se verifica siempre, con independencia de dónde se coloque;
- cada ficha exige el permiso de SU dominio (un nodo requiere `nodes.view`, no basta `assets.view`);
- la búsqueda transversal filtra en el servidor y omite lo que el usuario no podría abrir;
- proponer y confirmar son permisos distintos (reportar una incidencia ≠ resolverla);
- el área declarada de un perfil agrupa la navegación y **no otorga ningún permiso**;
- un widget que falle se aísla: no se filtran trazas ni errores de base de datos a la interfaz;
- la suite de pruebas no escribe dentro del árbol de código, de modo que una release
  instalada puede validarse sin debilitar permisos de `/opt`;
- UFW recomendado: 8080 sólo desde subred LAN autorizada; el instalador sólo liga la app a `0.0.0.0` cuando detecta UFW activo, de lo contrario queda en `127.0.0.1`.

## Límites de alpha

- HTTP LAN sin TLS; fuera de LAN usar VPN/HTTPS y cookie secure;
- sin MFA/SSO;
- sin rate-limit persistente de login;
- archivos sin antivirus/malware scanning todavía;
- E2E navegador físico pendiente;
- no abrir 5432 a la LAN ni 8080 a Internet;
- restore es una acción administrativa explícita, nunca automática.

## Revisión de esta versión

El detalle completo de la revisión de seguridad de alpha.4 —superficie añadida,
control de acceso, validación de entrada, inyección, auditoría y el tratamiento
del `PermissionError` sin debilitar permisos— está en
`reports/REPORTE_SEGURIDAD.md`.

## Datos humanos

La plataforma registra hechos/evidencia y no genera sanciones automáticas ni
scoring laboral opaco. Las excepciones de nodos asociadas a una persona se
presentan explícitamente como trazabilidad y nunca como imputación. El acceso debe seguir mínimo privilegio y las exportaciones deben limitarse al área competente.

## Equipos/vida útil

Una observación predictiva (por ejemplo salud/RUL de NodeHealth) no autoriza retiro automático. Se conserva fuente, versión y decisión humana.
