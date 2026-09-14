# 16 · Monorepo, backend, frontend y operación

## Por qué no hay carpetas `backend/` y `frontend/`

Server Oficina usa un **monorepo con monolito modular**. La separación es lógica:

```text
app/api/       backend HTTP / permisos
app/core/      configuración, seguridad, RBAC
app/db/        persistencia/modelo
app/services/  lógica de importación/eventos/auditoría
app/static/    frontend HTML/CSS/JS
```

FastAPI sirve `/static` y `/`. No se necesita Node en producción para ejecutar la UI; Node se instala/usa en alpha.2 sólo para validar sintaxis JavaScript.

## Validación por capa

### Backend

```bash
./scripts/verify-backend.sh
```

Prueba Python, API, reglas de dominio y suite pytest.

### Frontend

```bash
./scripts/verify-frontend.sh
```

Prueba sintaxis JS y contrato estático: elementos requeridos, endpoints mínimos, ausencia de CDN y ausencia de datos demo incrustados.

### Despliegue

```bash
./scripts/verify-deploy.sh
```

Valida shell y contrato de infraestructura.

### Todo

```bash
./VALIDAR_SERVER_OFICINA.sh
```

## Iniciadores “de operación”

No hay que recordar comandos largos:

```text
INICIAR_SERVER_OFICINA.sh
DETENER_SERVER_OFICINA.sh
REINICIAR_SERVER_OFICINA.sh
ESTADO_SERVER_OFICINA.sh
LOGS_SERVER_OFICINA.sh
ABRIR_SERVER_OFICINA.sh
VALIDAR_SERVER_OFICINA.sh
BACKUP_SERVER_OFICINA.sh
RESTORE_SERVER_OFICINA.sh
INSTALAR_EN_TABLETA.sh
```

## Política al ejecutar

- una acción por script;
- `set -euo pipefail` cuando corresponde;
- detenerse ante el primer error útil;
- no ocultar salida diagnóstica;
- no borrar datos como “arreglo” automático;
- no recrear PostgreSQL si ya existe persistencia válida;
- restore siempre explícito con ruta de backup.

## Artefactos de una entrega válida

Una release debe incluir:

- código;
- `VERSION`;
- `CHANGELOG.md`;
- `00_LEEME_PRIMERO.md`;
- documentación de decisiones/descartes/referencias;
- resultados de pruebas;
- scripts operativos;
- `MANIFEST.sha256`;
- `BUILD_INFO.json`;
- ZIP final reproducible sin `.git`, venv, caches, secretos ni datos reales.

## Gate de navegador

`VALIDAR_FRONTEND_E2E.sh` valida el flujo visible sobre una base temporal. No se mezcla con `VALIDAR_SERVER_OFICINA.sh` porque el E2E requiere navegador/Playwright; así un host sin navegador devuelve `BLOCKED` explícito en vez de degradar silenciosamente la validación del paquete.

## Operadores raíz visibles

Además del validador global, la raíz expone `VALIDAR_BACKEND.sh`, `VALIDAR_FRONTEND.sh`, `VALIDAR_DESPLIEGUE.sh` y `VALIDAR_FRONTEND_E2E.sh`. El objetivo es que una persona pueda ejecutar un gate por capa sin conocer rutas internas. También se incluye `INSTALAR_ACCESO_ESCRITORIO.sh` para recrear el acceso local sin reinstalar el servidor.
