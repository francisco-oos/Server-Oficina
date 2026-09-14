# 08 · Plan de pruebas y gates — alpha.2

## Suite heredada y revalidada

```text
pytest: 11 passed
compileall: OK
node --check app/static/app.js: OK
bash -n scripts/launchers: OK
```

## Validadores separados

```bash
./scripts/verify-backend.sh
./scripts/verify-frontend.sh
./scripts/verify-deploy.sh
./VALIDAR_SERVER_OFICINA.sh
```

### Backend

- health;
- bootstrap admin;
- usuario con rol;
- identidad estable/rehire;
- baja y recontratación por API;
- EPP supervisor solicita pero no valida;
- HR/Admin valida;
- importación XLSX PREVIEW→COMMIT + SHA;
- capacitación RRHH→HSE;
- caso sin sanción automática + resolución humana;
- reporte tardío `occurred_at` vs `recorded_at`.

### Frontend

- sintaxis JavaScript;
- IDs estructurales requeridos;
- contratos API mínimos presentes;
- ausencia de dependencias CDN en `index.html`;
- ausencia de datos demo incrustados conocidos.

Esto **no reemplaza E2E en navegador real**.

### Despliegue

- sintaxis de todos los operadores shell;
- contrato compose: PostgreSQL 18.6, bind localhost 5432 y persistencia `/srv`;
- service unit bajo usuario sin privilegios.

## Evidencia física ya conseguida durante preparación del host

- Docker/containerd arrancan después de reboot;
- Docker y containerd almacenan en `/srv/docker`;
- PostgreSQL 18.6 healthy;
- persistencia después de restart;
- pg_dump custom;
- pg_restore a base temporal.

## Gates pendientes antes de llamar 0.1 estable

- [ ] `INSTALAR_EN_TABLETA.sh` completo;
- [ ] app systemd tras reboot;
- [ ] bootstrap admin real;
- [ ] acceso PC + teléfono LAN;
- [ ] copia de Excel real Oficina: preview;
- [ ] resolver una ambigüedad/recontratación real;
- [ ] permisos HR/HSE/Supervisor reales;
- [ ] backup integral app+BD y restore integral;
- [ ] navegador E2E real;
- [ ] revisión de permisos/datos sensibles;
- [ ] estabilidad 24 h sin suspensión.

## Gate E2E de navegador

Se incluye `VALIDAR_FRONTEND_E2E.sh` / `scripts/verify-frontend-e2e.sh`. Arranca una instancia aislada con SQLite temporal y usa Playwright + Chromium/Chrome para recorrer: configuración inicial, login, dashboard, alta de persona, detalle y logout.

Este gate es adicional al contrato estático y al smoke HTTP. Si la máquina de validación carece de Playwright o navegador compatible, debe reportarse `E2E_BLOCKED`, nunca fingir PASS. El entorno de construcción de alpha.2 tiene Chromium administrado con `URLBlocklist=*`, por lo que el navegador local bloquea localhost; el runner quedó preparado para ejecutarse en la Latitude/QA host sin esa política.
