# Server Oficina 0.2.0-alpha.1 — candidato

Servidor de oficina LAN, trazabilidad e inteligencia documental **local-first**.
El núcleo conserva archivos, versiones, identidad, evidencia, consultas y
relaciones sin obligar a sustituir Excel/Word/PDF.

## Idea central

> **Archivo canónico; almacenamiento resoluble; base derivada; trazabilidad
> completa; IA como intérprete; humano y fuente competente como autoridad.**

Tracking Core relaciona personas, activos, documentos, eventos y evidencias.
La experiencia de cada dominio conserva su semántica: compartir trazabilidad no
significa usar la misma ficha ni el mismo flujo.

## Arquitectura actual

- Debian 13 en Dell Latitude 7220 como primer hub.
- FastAPI + SQLAlchemy.
- PostgreSQL en servicio local.
- PCs Windows con copias locales y sincronización LAN.
- Syncthing como transporte de la capa de archivos replicados.
- historial propio por SHA-256 y versiones auditables.
- Synology/NAS desacoplado del trabajo cotidiano.
- IA/LLM todavía fuera del gate de sincronización.

La Latitude es **el primer host**, no una dependencia arquitectónica permanente:
el rol podrá migrar a un NAS/servidor dedicado.

## Sincronización y usuarios

Cada PC tiene identidad propia y la persona que la usa inicia una sesión de
estación renovable como máximo cada 15 días. Esto permite atribuir operaciones
digitales y conocer presencia en equipos sin convertir ese dato en asistencia
oficial de RRHH.

Los usuarios autorizados pueden dar seguimiento transversal a los documentos
sincronizados. El área propietaria determina autoridad sobre un dato, no
aislamiento automático del documento.

## Almacenamiento

No todo archivo debe existir físicamente en todos los nodos. La dirección
aceptada distingue HOT/WARM/COLD:

- contenido activo/pequeño: réplica local;
- caché operativa: hub;
- contenido pesado/histórico: NAS primario;
- futuro Companion Windows: placeholders/hidratación bajo demanda.

Las políticas de tamaño y permanencia serán configurables; no se hardcodean.

## Núcleo reutilizable

El proyecto separará progresivamente:

`Core reutilizable + Domain Pack`.

El Core contiene sincronización, identidad, versiones, evidencia, grafo,
búsqueda, auditoría y dashboard. El perfil actual de Adquisición Sísmica aporta
vocabulario, formatos y reglas. Así el mismo núcleo puede adaptarse a otras
oficinas sin reentrenar un LLM ni bifurcar el motor.

## Pruebas

`./VALIDAR_SERVER_OFICINA.sh`

Además existe una integración real de tres procesos Syncthing en CI para create,
modify, rename, delete, conflicto offline, restart, lotes y verificación de hash.

No se promueve a producción por CI solamente: falta gate físico en Latitude y
PCs Windows.

## Documentación

Comience por:

- `docs/INICIO_RAPIDO.md`
- `docs/00_INDICE_DOCUMENTACION.md`
- `docs/vision/38_MISION_VISION_NUBE_LOCAL_IA.md`
- `docs/investigacion/47_ALMACENAMIENTO_JERARQUICO_ARCHIVOS_GRANDES.md`
- `docs/decisiones/48_ADR_ALMACENAMIENTO_JERARQUICO_Y_DOMAIN_PACKS.md`

Estado real: `docs/estado/14_MATRIZ_REQUISITOS_Y_ESTADO.md`.
Pendientes: `reports/PENDIENTES_REALES.md`.
