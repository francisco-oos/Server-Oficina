# Changelog

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
