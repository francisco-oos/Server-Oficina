# Changelog

## 0.1.0-alpha.3 — 2026-09-11

Evolución aditiva sobre la misma base alpha.2 instalada en la Latitude. Recupera los acuerdos de RRHH operativo, Material, Tracking Nodes, taller, inventario, evidencias y perfiles configurables sin crear un sistema paralelo.

### RRHH y administración
- categoría, licencia/vigencia, rotación trabajo/descanso y asignaciones temporales;
- organizaciones/outsourcing normalizados manteniendo compatibilidad con `provider`;
- eventos de renuncia, despido, fin de contrato y recontratación sobre la misma persona;
- perfiles de negocio configurables con matriz de permisos y protección del último ADMIN.

### Asset Core / Material
- tipos de activo y tecnologías configurables; reglas por capacidades, no por nombres hardcodeados;
- identificadores múltiples: serie, IMEI, QR, económico y futuros;
- custodia, proyecto, grupo, ubicación y movimientos con historial;
- carga masiva CSV con PREVIEW/COMMIT y conservación de columnas informativas extra;
- inventario físico con faltantes observados sin declarar automáticamente pérdida;
- cierre de proyecto mediante snapshot auditable y transferencia posterior sin reescribir el corte.

### Tracking Nodes
- operaciones por lote TENDIDO, ROTACION, LEVANTADO, RETORNO e INCIDENT;
- línea/estaca origen-destino, responsable, participantes y procedencia;
- resultados/estados probados: dañado, quemado, no encontrado, extraviado, robado, incautado, mantenimiento, hibernado y sin información;
- resultado de nodo se traduce a movimiento mediante metadatos de catálogo, no condicionales por string.

### Taller / vida útil
- órdenes de mantenimiento, diagnóstico, acción, resultado y downtime;
- componentes con serial retirado/instalado;
- observaciones SOH/RUL/health score con fuente/confianza;
- una predicción nunca cambia automáticamente el estado factual.

### Evidencias / NAS
- repositorios LOCAL/SMB configurables y fail-closed si el mount desaparece;
- upload en streaming con SHA-256, archivo temporal y promoción atómica;
- indexación de archivo que ya existe en NAS/Windows sin moverlo;
- scripts para montar NAS con credenciales root-only y bandeja Samba opcional en la Latitude;
- ninguna IP, letra de unidad o campamento histórico hardcodeado en la UI.

### UI
- navegación profesional por Operación / Oficina / Administración;
- dashboard de activos/excepciones/taller;
- localizador persona/activo;
- pantallas de Asset Core, nodos, mantenimiento, inventario, evidencias, perfiles, catálogos y cierre de proyecto;
- corrección de errores `[object Object]` y validación de contraseña inicial.

### Despliegue y QA
- backup `pg_dump -Fc` pre-upgrade antes de promover release;
- rollback de symlink `current` si `/api/health` falla;
- **27 pruebas automáticas** finales más compileall/JS/shell/contratos;
- E2E de navegador separado: primer admin → login → dashboard → persona → nodo → TENDIDO → logout.

## 0.1.0-alpha.2 — 2026-09-11

- Endurecimiento de empaquetado/despliegue sobre Latitude real.
- PostgreSQL 18.6 en Docker y datos bajo `/srv`.
- Aplicación host `systemd`, UFW LAN, iniciadores raíz, backup/restore y gates por capa.
- UI/Oficina/Personal funcionando físicamente y primer administrador validado desde navegador.
- Investigación/documentación inicial de Asset Core, vida útil y RRHH.

## 0.1.0-alpha.1 — 2026-09-10

Primer corte vertical instalable de Server Oficina.

### Core e infraestructura
- Tracking Core temporal con `OperationalEvent`, `occurred_at` y `recorded_at`.
- PostgreSQL como fuente de verdad de despliegue; SQLite únicamente para pruebas/local.
- FastAPI + SQLAlchemy + UI web estática.
- Login, sesiones opacas revocables y RBAC granular.
- Bootstrap de primer administrador de un solo uso.
- Roles iniciales: ADMIN, HR, HSE, OFFICE, SUPERVISOR.
- Auditoría, health, systemd, instalación Debian, backup/restore con hashes.

### Oficina / Personal
- Identidad de persona estable separada del ID laboral.
- Relaciones laborales, baja, recontratación y periodos/renovaciones de contrato.
- Proyectos y grupos temporales.
- Directorio/búsqueda/expediente y timeline.
- Importador XLSX/XLSM/CSV con preview/commit, original y SHA-256.
- Asistencia por columnas de fecha.
- EPP con solicitud separada de validación RRHH.
- Capacitación RRHH→HSE.
- Casos/evidencias con resolución humana y sin veredicto automático.

### Documentación
- Problemática/finalidad separada de decisiones y razonamiento.
- Arquitectura, modelo de datos, importación, instalación, pruebas, descartes y roadmap.
- Registro de repositorios propios y externos con snapshots/uso/adaptación.
- Regla explícita: estudiar/adaptar patrones, no copiar ni forzar la operación al producto externo.

### Verificación
- 11 pruebas automáticas aprobadas.
- Python compileall OK.
- JavaScript syntax check OK.
- Shell syntax check OK.
- Smoke local Uvicorn: `/api/health` y `/` HTTP 200.

### Pendiente antes de declarar 0.1 estable
- PostgreSQL/psycopg en Latitude física.
- systemd/reboot/LAN real.
- archivos reales de Oficina.
- backup+restore real.
- QA navegador y concurrencia física.
