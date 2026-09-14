# 08 · Plan de pruebas y gates

## Suite ejecutada en esta entrega

Entorno de construcción disponible: Python del contenedor, SQLite aislado para test.

Comandos:

```bash
pytest
python3 -m compileall -q app tests run.py
```

Resultado registrado al empaquetar:

- `7 passed`;
- `compileall`: OK;
- arranque Uvicorn local: OK;
- `GET /api/health`: HTTP 200.

## Casos cubiertos

1. health básico;
2. identidad estable al recontratar con ID laboral distinto;
3. un supervisor puede solicitar EPP pero recibe 403 al intentar validarlo;
4. HR/Admin puede validar y crea historial oficial EPP;
5. importación XLSX primero PREVIEW, luego COMMIT;
6. capacitación RRHH→HSE;
7. caso registra hecho y queda abierto sin sanción automática;
8. `occurred_at < recorded_at` en reporte tardío.

## Limitaciones de esta ejecución

El entorno de construcción no tuvo salida DNS para `pip`; por ello las dependencias se probaron con las versiones ya presentes en el entorno y SQLite. `psycopg` no estaba instalado allí. El instalador Debian sí declara `psycopg[binary]` y debe ejecutarse/validarse en la Latitude con PostgreSQL.

## Gates antes de 0.1 estable

- [ ] `pip install -r requirements.txt` en Debian físico;
- [ ] PostgreSQL real y migración/arranque;
- [ ] systemd tras reboot;
- [ ] acceso LAN concurrente;
- [ ] Excel real de Oficina: preview correcto;
- [ ] prueba de duplicado/recontratación real;
- [ ] EPP con usuarios HR/Supervisor reales;
- [ ] backup y restauración en host físico;
- [ ] Playwright/E2E básico en navegador real;
- [ ] revisión de permisos y datos sensibles.
