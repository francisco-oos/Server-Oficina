# Server Oficina 0.1.0-alpha.4

Servidor departamental LAN para Adquisición de Datos. Centraliza identidad
laboral, asistencia, proyectos, grupos, activos, nodos, transporte, custodia,
movimientos, mantenimiento, inventarios, cursos, EPP, casos y evidencias sin
destruir el historial operativo.

## Idea central

Server Oficina **no** es un conjunto de formularios CRUD independientes. Es un
sistema departamental de trazabilidad construido sobre un **Tracking Core**
común.

> Tracking Core es común por debajo, pero la experiencia de cada dominio refleja
> su realidad. RRHH sigue la vida laboral de una persona; Operación el ciclo de
> un nodo; Material la custodia y el inventario; Transporte las unidades y sus
> asignaciones; Taller el diagnóstico y la reparación. Todos se relacionan y
> forman una historia común, pero **sus fichas, acciones, estados y timelines no
> son intercambiables**.

## Arquitectura

- Debian 13 en Dell Latitude 7220.
- FastAPI + SQLAlchemy como monolito modular.
- Interfaz web estática servida por la misma aplicación, sin dependencias remotas.
- PostgreSQL 18.6 en Docker, sólo `127.0.0.1:5432`.
- Aplicación como servicio `systemd` sin privilegios.
- Datos en `/srv/server-oficina`; Docker/containerd en `/srv/docker`.

## Alcance

**Áreas**: Recursos Humanos · Seguridad/HSE · Transporte · Control de Material ·
Operación (Tracking Nodes) · Taller/TX · Administración.

- **RRHH**: persona con identidad estable, altas, bajas y recontrataciones,
  outsourcing, categoría, licencia y vigencia, rotación, asignaciones, asistencia y EPP.
- **Operación**: nodos por operación y lote —tendido, plantado, rotación,
  levantado, retorno— con sus excepciones y el estado derivado del historial.
- **Control de Material**: Asset Core con identificadores múltiples, custodia,
  entregas, transferencias, inventario físico y cierre auditable por proyecto.
- **Transporte**: unidades, conductores, asignaciones, radio y teléfono
  asociados, disponibilidad, checklist e incidencias.
- **Taller/TX**: órdenes, diagnóstico, piezas con serial retirado e instalado,
  resultado, downtime y observaciones de salud/RUL no autoritativas.
- **Evidencias**: repositorios LOCAL/SMB con SHA-256, fail-closed e indexación de
  archivos que ya viven en el NAS, sin moverlos.
- **Vista resumen configurable**: 28 widgets y 7 dashboards administrables desde
  un modo DEV, sin tocar código.

## Navegación

Doble, porque ambas hacen falta:

- **Por área**: quien trabaja en RRHH entra por RRHH; quien trabaja en
  Transporte, por Transporte. El menú se construye desde los permisos.
- **Transversal**: el buscador de la cabecera localiza persona, nodo, radio,
  teléfono, unidad, IMEI, QR, serie o número económico, y abre la ficha que
  corresponde a cada uno.

## Pruebas

```bash
./VALIDAR_SERVER_OFICINA.sh     # todos los gates + manifiesto
```

Gates por capa:

```bash
./VALIDAR_BACKEND.sh            # 62 pruebas + verificación sintáctica
./VALIDAR_FRONTEND.sh           # sintaxis JS + contrato de interfaz
./VALIDAR_DESPLIEGUE.sh         # sintaxis shell + contratos de despliegue
./VALIDAR_FRONTEND_E2E.sh       # recorrido de navegador (requiere Chromium)
```

Todos pueden ejecutarse sobre una release instalada en **modo sólo lectura**: la
suite no escribe nada dentro del árbol de código. Ver
`docs/35_TESTING_Y_RUNTIME.md`.

## Actualizar la tableta

```bash
./INSTALAR_EN_TABLETA.sh
```

Valida la release, crea un `pg_dump` pre-upgrade, conserva el `current`
anterior, promueve la versión nueva y revierte el puntero si el health check
falla. Esta versión **sólo agrega tablas**, por lo que `create_all` actualiza el
esquema sin migración manual.

## Evidencias / NAS

No hay rutas UNC ni campamentos en el código. Configure un repositorio desde la
interfaz y, si es SMB:

```bash
./CONFIGURAR_NAS_EVIDENCIAS.sh
```

Los archivos pesados pueden quedarse en el NAS; Server Oficina registra su
relación con la entidad, la ruta, el hash, el tamaño, el MIME, la procedencia y
el usuario.

## Documentación

Comience por `00_LEEME_PRIMERO.md` y `docs/00_INDICE_DOCUMENTACION.md`.

Para desarrollar: `docs/33_GUIA_DESARROLLO_MULTIDESARROLLADOR.md`.

Estado real de cada requisito: `docs/14_MATRIZ_REQUISITOS_Y_ESTADO.md`.
Lo que sigue pendiente: `reports/PENDIENTES_REALES.md`.
