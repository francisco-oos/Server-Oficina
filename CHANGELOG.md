# Changelog

## 0.2.0-alpha.1 — candidato 2026-09-21

Evolución local-first sobre 0.1.0-alpha.4. Los formatos de oficina continúan
siendo entregables canónicos; Server Oficina añade sincronización, versionado,
contexto verificable e interpretación local sin obligar a reemplazar Excel.

### Nube local
- modelo aditivo de equipos, carpetas, documentos y DAG de versiones;
- topología estrella prevista: PCs ↔ Latitude; Synology como réplica separada;
- watcher de dos pasadas para no ingerir un archivo mientras Office lo escribe;
- borrado lógico/tombstone: no existe purge físico automático;
- API y adaptador Syncthing restringido a loopback/red privada.

### Concurrencia
- leases cooperativos de edición con TTL;
- version vectors para distinguir BEFORE/AFTER/EQUAL/CONCURRENT;
- merge semántico 3-way inspirado en Git únicamente para registros con clave
  estable;
- conflicto explícito si dos lados cambian el mismo campo;
- nunca se fusionan bytes XLSX de forma ciega.

### Inteligencia documental
- reglas aprendidas por área/familia/contexto;
- aclaraciones conversacionales persistentes, p. ej. una columna nueva;
- hechos extraídos con tiempo, confianza y versión documental fuente;
- endpoint LLM local fail-closed: URLs públicas se rechazan;
- el modelo no escribe directamente en las tablas de dominio.

### Grafo
- proyección temporal sobre hechos documentales con procedencia hasta
  documento/versión/hash;
- búsqueda de vecindad sin introducir todavía una segunda base de grafos.

### Calidad
- simulación automatizada de 24 clientes, leases y concurrencia;
- pruebas de aprendizaje/correcciones, grafo, privacidad y watcher;
- CI Python 3.12/3.13;
- despliegue de laboratorio separado del instalador productivo.

## 0.1.0-alpha.4 — 2026-09-14

Revisión, corrección y evolución de **la misma base alpha.3**. No se creó un
proyecto paralelo, no se sustituyó FastAPI/PostgreSQL y no se rehízo el dominio.
El eje del trabajo fue cerrar la brecha entre lo que el sistema modela y lo que
la interfaz presentaba, más tres requisitos nuevos.

### Vista resumen configurable (modo DEV)
- registro de **28 widgets** en código, separado de su configuración en base de datos;
- **7 vistas resumen**: una general y una por área, todas configurables;
- modo DEV para mostrar, ocultar, ordenar, redimensionar, retitular y restringir por perfil;
- creación, activación y borrado de vistas resumen propias;
- la configuración **acota pero nunca amplía** privilegios: el permiso del widget siempre manda;
- un widget que falle se aísla y no tumba la pantalla del operador;
- la siembra de arranque ya no pisa lo que configuró el administrador;
- documentado cómo crear un widget nuevo sin tocar el endpoint ni la interfaz.

### Dominio de Transporte
- `transport_assignments`, `transport_checklists` y `transport_incidents`;
- vínculo temporal unidad ↔ conductor ↔ grupo ↔ proyecto ↔ radio ↔ teléfono;
- la unidad, el radio y el teléfono **son** activos del Asset Core: no se duplican registros;
- reasignar cierra la asignación anterior con fecha en lugar de sobrescribirla;
- checklist con hallazgos que **no** inmoviliza la unidad automáticamente;
- incidencias que cualquier área puede reportar y sólo Transporte resuelve;
- ficha de unidad, listado de flota, checklist e incidencias en la interfaz.

### Autoridad sobre el dato por área
- 7 áreas y **15 dominios de información** con autoridad, consulta, propuesta y confirmación;
- distinción explícita **proponer ≠ confirmar**, materializada en permisos separados;
- área declarable por perfil (`role_areas`), que agrupa la navegación y **nunca** autoriza;
- matriz consultable desde API y desde la interfaz, leída de la misma fuente que la documentación.

### Interfaz reconstruida
- **navegación doble**: por área en la barra lateral y transversal por el buscador;
- el menú se construye desde los permisos: desaparecen las entradas que darían 403;
- **cuatro fichas específicas por dominio** —persona, nodo, activo y unidad— que ya no son intercambiables;
- expediente de persona con el bloque de localización completo (estado, grupo, responsable, unidad, conductor, radio, teléfono, ubicación, proyecto);
- ficha de nodo con su ciclo operacional y el estado actual **junto a su derivación**;
- búsqueda transversal que localiza por nombre, ID laboral, serie, IMEI, QR o número económico y abre la ficha correcta, indicando por qué coincidió;
- vista resumen que responde qué pasa, qué requiere atención, qué cambió, qué está pendiente y **qué debo atender yo**;
- **diseño responsive** real (3 puntos de quiebre) para tableta y teléfono;
- los datos no capturados se distinguen de los vacíos;
- `app.js` pasa de 170 líneas ilegibles a 2 450 estructuradas y comentadas en español.

### Corrección del `PermissionError` en validación manual
- las pruebas ya no escriben **nada** dentro del árbol de código;
- runtime temporal configurable con `SERVER_OFICINA_TEST_RUNTIME`;
- `scripts/syntax-check.py` sustituye a `compileall`, que escribía `__pycache__`;
- caché de pytest desactivada por defecto;
- corregido **sin** `chmod -R 777` y sin debilitar permisos de `/opt`;
- verificado con árbol en sólo lectura y usuario sin privilegios.

### Catálogos y correcciones
- añadidos `PLANTADO` y `ALMACENADO`/`STORED`, que faltaban entre los eventos de nodo;
- las capacidades `radio` y `phone` sustituyen tres decisiones tomadas por nombre de tipo;
- la siembra ahora **incorpora** capacidades nuevas a tipos ya existentes al actualizar;
- restaurado el bit de ejecución de los `*.sh`, perdido en el versionado;
- eliminadas 22 importaciones sin usar; análisis estático limpio.

### Pruebas
- **62 pruebas** (27 heredadas intactas + 35 nuevas), **0 regresiones**;
- el **gate E2E de navegador se ejecuta de verdad**, incluida la comprobación responsive a 390 px y la vigilancia de errores de consola;
- pruebas específicas de escalada de privilegios, aislamiento de fallos y no-sobrescritura de configuración.

### Documentación
- 10 documentos nuevos: Tracking Core, modelo de dominio por área, autoridad del dato, dashboard configurable y registro de widgets, arquitectura de interfaz, referencia de API, guía multidesarrollador, contrato de ingesta documental, pruebas/runtime y respaldo/restauración;
- índice reescrito y matriz de requisitos con estado real, prueba que lo demuestra y archivos relacionados;
- reportes PRE, POST, cambios de interfaz, pruebas, seguridad, revisión independiente y pendientes reales.

### Compatibilidad
- **sólo se agregaron tablas**; ninguna existente cambió de forma, así que `create_all` promueve la instalación sin migración manual;
- `GET /api/health`, `GET /api/dashboard` y `GET /api/locate` conservados.

## 0.1.0-alpha.3 — 2026-09-11

Evolución aditiva sobre la misma base alpha.2 instalada en la Latitude. Recupera los acuerdos de RRHH operativo, Material, Tracking Nodes, taller, inventario, evidencias y perfiles configurables sin crear un sistema paralelo.

### RRHH y administración
- categoría, licencia/vigencia, rotación trabajo/descanso y asignaciones temporales;
- organizaciones/outsourcing normalizados manteniendo compatibilidad con `provider`;
- eventos de renuncia, despido, fin de contrato y recontratación sobre la misma persona;
- perfiles de negocio configurables con matriz de permisos y protección del último ADMIN.

### Asset Core / Material
- tipos de activo y tecnologías configurables; reglas por capacidades, no por nombres hardcodeados;
- identificadores múltiples: serie, IMEI, QR, económico y futuros;
- custodia, proyecto, grupo, ubicación y movimientos con historial;
- carga masiva CSV con PREVIEW/COMMIT y conservación de columnas informativas extra;
- inventario físico con faltantes observados sin declarar automáticamente pérdida;
- cierre de proyecto mediante snapshot auditable y transferencia posterior sin reescribir el corte.

### Tracking Nodes
- operaciones por lote TENDIDO, ROTACION, LEVANTADO, RETORNO e INCIDENT;
- línea/estaca origen-destino, responsable, participantes y procedencia;
- resultados/estados probados: dañado, quemado, no encontrado, extraviado, robado, incautado, mantenimiento, hibernado y sin información;
- resultado de nodo se traduce a movimiento mediante metadatos de catálogo, no condicionales por string.

### Taller / vida útil
- órdenes de mantenimiento, diagnóstico, acción, resultado y downtime;
- componentes con serial retirado/instalado;
- observaciones SOH/RUL/health score con fuente/confianza;
- una predicción nunca cambia automáticamente el estado factual.

### Evidencias / NAS
- repositorios LOCAL/SMB configurables y fail-closed si el mount desaparece;
- upload en streaming con SHA-256, archivo temporal y promoción atómica;
- indexación de archivo que ya existe en NAS/Windows sin moverlo;
- scripts para montar NAS con credenciales root-only y bandeja Samba opcional en la Latitude;
- ninguna IP, letra de unidad o campamento histórico hardcodeado en la UI.

### UI
- navegación profesional por Operación / Oficina / Administración;
- dashboard de activos/excepciones/taller;
- localizador persona/activo;
- pantallas de Asset Core, nodos, mantenimiento, inventario, evidencias, perfiles, catálogos y cierre de proyecto;
- corrección de errores `[object Object]` y validación de contraseña inicial.

### Despliegue y QA
- backup `pg_dump -Fc` pre-upgrade antes de promover release;
- rollback de symlink `current` si `/api/health` falla;
- **27 pruebas automáticas** finales más compileall/JS/shell/contratos;
- E2E de navegador separado: primer admin → login → dashboard → persona → nodo → TENDIDO → logout.

## 0.1.0-alpha.2 — 2026-09-11

- Endurecimiento de empaquetado/despliegue sobre Latitude real.
- PostgreSQL 18.6 en Docker y datos bajo `/srv`.
- Aplicación host `systemd`, UFW LAN, iniciadores raíz, backup/restore y gates por capa.
- UI/Oficina/Personal funcionando físicamente y primer administrador validado desde navegador.
- Investigación/documentación inicial de Asset Core, vida útil y RRHH.

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
