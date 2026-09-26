# 08 · Plan de pruebas y gates — alpha.3

## Gate base

`VALIDAR_SERVER_OFICINA.sh` ejecuta validación de backend, frontend, despliegue e integridad. El E2E de navegador es un gate separado porque requiere Playwright/Chromium real.

## Backend

La suite final de construcción contiene **27 pruebas** y cubre, entre otros:

- bootstrap/login/RBAC y protección del último ADMIN;
- identidad persona→baja/rehire;
- categoría, licencia/vigencia, rotación, asistencia;
- cursos, EPP y casos sin sanción automática;
- empresas/outsourcing normalizados;
- activos con serie/IMEI/QR/económico;
- tipos/tecnologías/estados futuros creados sin modificar Python;
- custodia y localizador;
- TENDIDO→ROTACION→LEVANTADO→RETORNO;
- DAMAGED/BURNED/MISSING/LOST/STOLEN/SEIZED/MAINTENANCE/HIBERNATED/NO_INFO;
- mantenimiento, piezas, downtime y RUL no-autoritativo;
- inventario físico y faltantes;
- importación masiva con metadata extra;
- evidencias locales, SMB fail-closed e indexación de archivo ya existente;
- cierre auditable de proyecto y transferencia posterior sin reescribir snapshot;
- historia de aceptación transversal RRHH + material + nodos + taller + inventario + cierre.

## Frontend

- `node --check app/static/app.js`;
- contrato estructural y endpoints mínimos;
- errores FastAPI legibles (no `[object Object]`);
- sin CDN;
- sin rutas históricas/IP de campamento hardcodeadas;
- formularios para Asset Core, Node Tracking, mantenimiento, inventario, evidencias, tipos/tecnologías, perfiles y corte de proyecto.

## Despliegue

- sintaxis shell de operadores e instaladores;
- PostgreSQL 18.6 en Docker con persistencia `/srv` y bind loopback;
- app host `systemd`;
- backup pre-upgrade antes de promover release;
- rollback de symlink si health falla;
- scripts SMB guardan credenciales root-only.

## Navegador E2E

`VALIDAR_FRONTEND_E2E.sh` recorre primer administrador, login, dashboard, alta de persona, alta de nodo, TENDIDO y logout. Si el entorno bloquea Chromium, debe reportar `E2E_BLOCKED`; no se convierte en PASS ficticio.

## Gates físicos ya verificados en la Latitude con alpha.2

Instalación de alpha.2, primer administrador, acceso LAN, `server-oficina.service`, PostgreSQL/Docker en `/srv`, UFW y operación web fueron comprobados durante la sesión real. Alpha.3 aún debe instalarse como actualización después de la supervisión del paquete.
