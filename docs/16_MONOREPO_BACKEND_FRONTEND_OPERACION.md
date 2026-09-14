# 16 · Monorepo, backend, frontend y operación

Server Oficina continúa como **monorepo con monolito modular**:

```text
app/api/       HTTP / permisos / contratos
app/core/      seguridad, configuración, RBAC
app/db/        modelos/persistencia
app/services/  bootstrap, importaciones, eventos, auditoría
app/static/    frontend HTML/CSS/JS
scripts/       operación, validación, NAS y despliegue
tests/         backend + aceptación + E2E
```

No hay segundo servidor frontend; FastAPI sirve la UI. Node sólo se usa para `node --check`, no es dependencia de runtime del navegador.

## Operadores raíz

Iniciar, detener, reiniciar, estado, logs, abrir, validar, backup, restore, instalar, configurar NAS y configurar bandeja de evidencias tienen wrappers visibles en la raíz para no depender de comandos memorizados.

## Gates

- `VALIDAR_BACKEND.sh`: Python/suite;
- `VALIDAR_FRONTEND.sh`: JS + contrato UI/API;
- `VALIDAR_DESPLIEGUE.sh`: shell/infra/upgrade/NAS;
- `VALIDAR_FRONTEND_E2E.sh`: navegador real;
- `VALIDAR_SERVER_OFICINA.sh`: paquete base completo.

## Release válida

Incluye código, versión, changelog, documentación, resultados, scripts, tests, `MANIFEST.sha256` y `BUILD_INFO.json`; excluye `.git`, venv, caches, secretos y datos reales.

## Política operacional

Scripts usan `set -euo pipefail` cuando corresponde, no borran datos como reparación automática y requieren restore explícito. Actualizar alpha.3 crea backup antes de promover `current` y mantiene la release anterior disponible para rollback.
