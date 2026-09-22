# Server Oficina 0.2.0-alpha.1 — candidato

Servidor departamental LAN y **nube local privada** para Adquisición de Datos.
Centraliza identidad laboral, activos, nodos, transporte, evidencias y contexto
operativo sin sustituir Excel/Word/PDF ni destruir el historial.

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


## Nube Local 0.2

La Latitude + SSD pasa a ser el hub operativo local de la oficina:

```text
PCs de oficina ⇄ sincronización LAN ⇄ Latitude + SSD
                                      ├─ archivos canónicos/versiones
                                      ├─ Tracking Core + PostgreSQL
                                      ├─ grafo temporal derivado
                                      ├─ inteligencia documental local
                                      └─ réplica → Synology cuando esté disponible
```

Regla de producto: **el archivo es canónico; la base es una proyección
verificable; la IA interpreta pero no recuerda ni decide por sí sola**.

La primera candidata usa Syncthing como transporte LAN, leases cooperativos para
prevenir doble escritura, preservación de conflictos y merge semántico de tres
vías sólo para familias estructuradas con clave estable. El NAS/Internet no son
requisito para que la oficina siga trabajando.

Vea `docs/38_MISION_VISION_NUBE_LOCAL_IA.md` a
`docs/44_INVESTIGACION_SINCRONIZACION_IA_GRAFOS.md`.

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
./VALIDAR_BACKEND.sh            # suite histórica + nube local + sintaxis
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
falla. Esta candidata mantiene cambios de esquema **aditivos**. No se promueve a la
tableta productiva hasta superar CI, prueba física, rollback/restore y ensayo
de sincronización en una carpeta LAB.

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

Comience por `docs/INICIO_RAPIDO.md` y `docs/00_INDICE_DOCUMENTACION.md`.

Para desarrollar: `docs/33_GUIA_DESARROLLO_MULTIDESARROLLADOR.md`.

Estado real de cada requisito: `docs/14_MATRIZ_REQUISITOS_Y_ESTADO.md`.
Lo que sigue pendiente: `reports/PENDIENTES_REALES.md`.
