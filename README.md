# Server Oficina 0.1.0-alpha.1

Primer candidato instalable del sistema acordado para **Adquisición de Datos**. La entrega visible es **Oficina / Personal** y debajo queda el **Tracking Core** temporal/auditable para crecer después a Control de Material, nodos, TX, Taller/Mantenimiento, Transporte, Seguridad/HSE y Supervisión.

## Qué resuelve ya

- Login, sesiones opacas revocables y RBAC granular.
- Primer administrador creado desde navegador; luego el bootstrap se bloquea.
- Alta de usuarios por rol (`ADMIN`, `HR`, `HSE`, `OFFICE`, `SUPERVISOR`).
- Dashboard de Oficina calculado desde la base.
- Personas separadas de sus IDs/relaciones laborales: baja y recontratación pueden cambiar ID sin duplicar identidad.
- Periodos/renovaciones contractuales listos para outsourcing.
- Proyectos y grupos como relaciones temporales.
- Directorio, búsqueda por nombre/ID laboral y expediente con timeline.
- Importación XLSX/XLSM/CSV con **preview antes de commit**, SHA-256 y archivo original conservado.
- Asistencia por columnas de fecha.
- EPP: usuario autorizado solicita; **sólo RRHH/rol con `epp.validate_hr` valida**.
- Capacitación: RRHH programa/lista; HSE confirma recibido/completado.
- Casos/evidencias: se documentan hechos; la resolución humana está separada y no existe sanción automática.
- Eventos con `occurred_at` / `recorded_at`, auditoría y procedencia.
- Health check, scripts Debian, systemd, backup y restore.
- UI web responsive sin build frontend pesado.
- Cero datos reales hardcodeados.

## Estructura

```text
app/
  api/          API y permisos
  core/         configuración, seguridad y RBAC
  db/           modelo relacional
  services/     importación, eventos, auditoría, bootstrap
  static/       dashboard/UI web
scripts/        instalación, backup, restore, smoke
deploy/         unidades systemd
docs/           problema, arquitectura, decisiones, referencias, descartes, modelo y roadmap
references/     registro machine-readable de repositorios revisados
tests/          pruebas automáticas
```

## Prueba local de desarrollo

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
python run.py
```

Abre `http://127.0.0.1:8080`.

## Instalación en Latitude / Debian

Cuando Debian esté listo, descomprime este ZIP y desde la raíz ejecuta:

```bash
sudo bash scripts/install-debian.sh
```

El instalador prepara PostgreSQL, directorios persistentes, servicio systemd y backup diario. Después abre `http://IP_DE_LA_TABLET:8080` y crea el primer administrador.

Guía: `docs/07_INSTALACION_DEBIAN.md`.

## Estado de pruebas de esta entrega

- `pytest`: **11 passed**.
- `compileall`: OK.
- `node --check app/static/app.js`: OK.
- `bash -n scripts/*.sh`: OK.
- arranque Uvicorn local/SQLite: OK.
- `GET /api/health`: HTTP 200.
- `GET /`: HTTP 200.

**Gate pendiente:** PostgreSQL/`psycopg`, systemd, reboot, LAN, archivos reales y backup/restore en la Latitude física. El entorno de construcción no tuvo DNS para instalar dependencias nuevas, por lo que esas pruebas deben ejecutarse en el host Debian.

## Documentación de mantenimiento

Empieza por:

1. `docs/01_PROBLEMA_Y_FINALIDAD.md`
2. `docs/02_ARQUITECTURA.md`
3. `docs/03_DECISIONES_Y_RAZONAMIENTO.md`
4. `docs/04_REFERENCIAS_REPOSITORIOS.md`
5. `docs/05_DESCARTES.md`
6. `TEST_RESULTS.md`

### Política de referencias

No se está adaptando la operación a Snipe-IT, Ralph, GLPI, OpenBoxes ni otro producto existente. Se estudian sus patrones y se implementa una solución propia para el dominio real. Toda incorporación futura de código/dependencias externas debe registrar commit, licencia, procedencia, motivo y pruebas.
