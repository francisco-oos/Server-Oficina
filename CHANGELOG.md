# Changelog

## 0.1.0-alpha.2 — 2026-09-11

- Se amplía investigación de vida útil con ISO 17359:2018, ISO 13379-1:2025 e ISO 13381-1:2025; RUL queda versionado/proveniente y nunca como sentencia automática.
- Se añade gate E2E reproducible de navegador (`VALIDAR_FRONTEND_E2E.sh`) separado del gate base.

Endurecimiento de entrega y despliegue sobre la Latitude real, sin crear un sistema paralelo.

### Despliegue/operación
- Canoniza PostgreSQL 18.6 en Docker con datos en `/srv/server-oficina/data/postgres`.
- PostgreSQL publicado sólo en `127.0.0.1:5432` para la aplicación host.
- Aplicación versionada bajo `/opt/server-oficina/releases/<VERSION>` + symlink `current`.
- Servicio `systemd` actualizado para Docker/PostgreSQL y datos en `/srv`.
- Iniciadores: iniciar, detener, reiniciar, estado, logs, abrir, validar, backup, restore e instalar.
- Backup/restore adaptado a contenedor PostgreSQL y evidencia/importaciones.
- UFW: script para permitir 8080 sólo desde la subred LAN actual.

### Calidad
- Validación separada de backend, frontend y despliegue.
- Contrato frontend: IDs requeridos, endpoints mínimos, sin recursos CDN ni datos demo incrustados.
- Health usa `app.__version__` en lugar de versión hardcodeada.
- Documentación de pruebas corregida de 7 a 11 tests heredados.

### Investigación/documentación
- ISO 55000:2024, ISO 14224:2016 y GS1 EPCIS 2.0 como referencias conceptuales para Asset Core.
- HR Open Standards/JEDx y contexto STPS para RRHH operativo/capacitación/EPP.
- Diseño de vida útil basado en edad + uso + condición + fallas + mantenimiento + RUL con procedencia, no en un solo campo.
- Matriz requisito→estado y gates por módulo.

### No cambiado
- No se agregan todavía tablas de Asset Core/Nodos/Taller.
- No se modifica el contrato de identidad persona/engagement.
- No se introducen microservicios ni frontend pesado.

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
