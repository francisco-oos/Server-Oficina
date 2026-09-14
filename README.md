# Server Oficina 0.1.0-alpha.2

Candidato instalable y auditable del sistema **Server Oficina** para Adquisición de Datos. Esta versión conserva el corte funcional de **Oficina / Personal + Tracking Core** de alpha.1 y añade el endurecimiento de entrega/despliegue requerido para la Latitude 7220 real.

## Arquitectura

Monorepo, monolito modular:

```text
Navegador LAN
   ↓
FastAPI + UI web estática
   ├── Auth / RBAC
   ├── Oficina / Personal
   ├── Importaciones
   ├── EPP
   ├── Capacitación
   ├── Casos / Evidencia
   └── Tracking Core
   ↓
PostgreSQL 18.6 en Docker
   ↓
/srv/server-oficina
```

No hay un frontend React/Vite separado. `app/static/` es el frontend y FastAPI lo sirve directamente.

## Qué resuelve ya

- login, sesiones opacas revocables y RBAC granular;
- primer administrador creado desde navegador y bootstrap de un solo uso;
- roles `ADMIN`, `HR`, `HSE`, `OFFICE`, `SUPERVISOR`;
- personas separadas de IDs/relaciones laborales;
- baja y recontratación con nuevo ID sin duplicar persona;
- renovaciones/periodos de outsourcing;
- proyectos y grupos temporales;
- directorio, búsqueda por nombre/ID y expediente/timeline;
- importación XLSX/XLSM/CSV con PREVIEW→COMMIT, SHA-256 y archivo original;
- asistencia;
- EPP con solicitud separada de validación RRHH;
- capacitación RRHH→HSE;
- casos/evidencias sin sanción automática;
- `occurred_at` separado de `recorded_at`;
- auditoría;
- backup/restore;
- UI responsive sin build frontend pesado;
- cero datos reales hardcodeados.

## Qué aporta alpha.2

- despliegue adaptado a Debian 13 + Docker/PostgreSQL ya preparado en la Latitude;
- PostgreSQL/Docker en `/srv`, no en el pequeño `/var`;
- Postgres sólo expuesto a `127.0.0.1:5432` para la aplicación host;
- servicio `systemd` sin privilegios;
- iniciadores raíz `INICIAR/DETENER/REINICIAR/ESTADO/LOGS/ABRIR/VALIDAR/BACKUP/RESTORE/INSTALAR`;
- validadores explícitos `VALIDAR_BACKEND`, `VALIDAR_FRONTEND`, `VALIDAR_DESPLIEGUE` y `VALIDAR_FRONTEND_E2E`;
- validadores separados de backend, frontend y despliegue;
- acceso LAN 8080 restringible por UFW a la subred actual;
- documentación nueva sobre ciclo de vida/vida útil de equipos y RRHH operativo;
- matriz requisito→estado para impedir declarar funciones incompletas como terminadas.

## Orden de lectura

Empieza por `00_LEEME_PRIMERO.md`.

## Validación local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
./VALIDAR_SERVER_OFICINA.sh
# Gate opcional pero explícito de navegador:
./VALIDAR_FRONTEND_E2E.sh
```

## Instalación en la Latitude preparada

Desde la raíz descomprimida:

```bash
./INSTALAR_EN_TABLETA.sh
```

El instalador **no instala PostgreSQL nativo**. Reutiliza/canoniza PostgreSQL 18.6 en Docker con persistencia en `/srv/server-oficina/data/postgres`, instala la aplicación versionada en `/opt/server-oficina/releases/<VERSION>`, crea `/opt/server-oficina/current`, configura `systemd` y prueba `/api/health`.

Después:

```bash
./ESTADO_SERVER_OFICINA.sh
./ABRIR_SERVER_OFICINA.sh
```

## Operación rápida

```bash
./INICIAR_SERVER_OFICINA.sh
./DETENER_SERVER_OFICINA.sh
./REINICIAR_SERVER_OFICINA.sh
./LOGS_SERVER_OFICINA.sh
./BACKUP_SERVER_OFICINA.sh
```

## Investigación y evolución

- `docs/12_INVESTIGACION_CICLO_VIDA_ACTIVOS.md`
- `docs/13_INVESTIGACION_RRHH_OPERATIVO.md`
- `docs/14_MATRIZ_REQUISITOS_Y_ESTADO.md`
- `docs/15_CONTRATOS_Y_GATES_MODULARES.md`

La investigación **no adelanta tablas paralelas** en esta alpha. El siguiente módulo se agrega sólo después de cerrar gates del bloque actual.

## Política de referencias

Los repositorios/estándares externos se estudian para patrones. No se fuerza la operación a Snipe-IT, Ralph, GLPI, OpenBoxes, HR Open u otro producto. Código externo sólo puede incorporarse con licencia, commit, procedencia, motivo y pruebas documentados.
