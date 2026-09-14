# Server Oficina 0.1.0-alpha.3

Servidor departamental LAN para Adquisición de Datos. Centraliza identidad laboral, asistencia, proyectos, grupos, activos, nodos, custodia, movimientos, mantenimiento, inventarios, cursos, EPP, casos y evidencias sin destruir el historial operativo.

## Arquitectura

- Debian 13 en Dell Latitude 7220.
- FastAPI + SQLAlchemy como monolito modular.
- UI web estática servida por la misma aplicación.
- PostgreSQL 18.6 en Docker, sólo `127.0.0.1:5432`.
- aplicación como servicio `systemd` sin privilegios.
- datos en `/srv/server-oficina` y Docker/containerd en `/srv/docker`.

## Alcance alpha.3

- RRHH operativo: persona estable, altas/recontrataciones, outsourcing, categoría, licencia, rotación, asignaciones temporales y asistencia.
- perfiles/roles configurables y permisos granulares.
- tipos/tecnologías/estados/ubicaciones configurables; no dependen de nombres de campamentos hardcodeados.
- Asset Core con múltiples identificadores y custodia.
- Tracking Nodes: TENDIDO, ROTACIÓN, LEVANTADO, RETORNO y excepciones.
- taller/mantenimiento y observaciones de salud/RUL.
- inventario físico, conciliación de faltantes y corte auditable de material por proyecto.
- repositorios de evidencia LOCAL/SMB con SHA-256, fail-closed e indexación de archivos ya existentes sin moverlos.
- carga masiva CSV de activos con preservación de columnas informativas como metadatos.

## Pruebas

Ejecutar:

```bash
./VALIDAR_SERVER_OFICINA.sh
```

Gates separados:

```bash
./VALIDAR_BACKEND.sh
./VALIDAR_FRONTEND.sh
./VALIDAR_DESPLIEGUE.sh
./VALIDAR_FRONTEND_E2E.sh   # requiere Chromium/Chrome + Playwright
```

El backend incluye **27 pruebas**: identidad/recontratación, EPP, cursos, asistencia, empresas/outsourcing, RRHH ampliado, perfiles, nodos Sercel/INOVA, tecnología futura, inventario, pérdida/incautación/quemado/hibernación, mantenimiento, carga de metadatos, evidencias, cierre de proyecto y una historia de aceptación transversal.

## Actualizar la tableta

```bash
./INSTALAR_EN_TABLETA.sh
```

El instalador valida la release, crea un `pg_dump` pre-upgrade, conserva el `current` anterior, promueve alpha.3 y revierte el puntero de release si el health check falla.

## Evidencias / NAS

No hay rutas UNC ni campamentos hardcodeados. Configure un repositorio desde la UI y, si es SMB:

```bash
./CONFIGURAR_NAS_EVIDENCIAS.sh
```

Opcionalmente puede crear una bandeja Windows ligera en la propia tableta:

```bash
./CONFIGURAR_BANDEJA_EVIDENCIAS.sh
```

Los archivos pesados pueden permanecer en NAS. Server Oficina registra relación con entidad/proyecto, ruta, hash, tamaño, MIME, procedencia y usuario.

## Documentación

Comience por `00_LEEME_PRIMERO.md` y `docs/00_INDICE_DOCUMENTACION.md`.
