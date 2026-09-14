# 04 · Registro de referencias y repositorios

**Regla:** una referencia no equivale a una dependencia. Se documenta URL, snapshot revisado, patrón aprendido, adaptación y decisión de incorporación/descartes. Esta alpha contiene implementación original y no copia módulos de terceros.

## Proyectos propios: evidencia operativa que sí define requisitos

| Repositorio | Snapshot revisado | Qué aporta | Adaptación en Server Oficina |
|---|---|---|---|
| https://github.com/francisco-oos/Formatos-HSE-Campo | `0786c7d5a9c26e32a3f6e06ed26be662bad21e7d` + README actual revisado 2026-09-10 | Android/Kotlin, PDF, QR, JSON AES-256-GCM embebido, SHA-256, fotos, perfil operativo | Futuro adaptador HSE: el PDF permanece evidencia humana y el payload estructurado podrá producir eventos verificables. **No se integra todavía.** |
| https://github.com/francisco-oos/SupervisionSeguraManage | `abe5418b47d7b0e20818267a3f4be539075310e1` | extracción/descifrado del JSON, normalización, PDF original + payload + hashes | Patrón directo de procedencia/evidencia. En el futuro se trasladará el concepto a PostgreSQL/Tracking Core, no se incrusta la aplicación PySide6. |
| https://github.com/francisco-oos/Tendido-Diario-revision | `42da7d48bc0d7e722c81b7c9a665e9b2f37993e2` | conciliación Sercel/INOVA/comentarios, prioridad de fuentes, claves por punto, histórico y cambios | Referencia para futuro módulo Material/Nodos y motor de contradicciones. No se copia el motor actual a Oficina 0.1. |
| https://github.com/francisco-oos/NodeHealthAnalyzer | `b7afbe41c0a7d7e458747e8afe271fc3c670d016` | importación masiva de CSV, histórico de nodos, analítica/mantenimiento | Referencia futura para estado técnico/mantenimiento predictivo; fuera del primer corte vertical. |
| https://github.com/francisco-oos/EventEstudio | baseline `a20066c2f5bb7b91d66434190bf10db1e4607334` | experiencia real con backend web, cuentas/roles, seguridad, restauración, regresiones, despliegue | Se adoptan **principios** de permisos, pruebas de regresión, backups/restore y no destruir datos. No se reutiliza su dominio ni DB. |

## Repositorios externos estudiados

| Repositorio | Snapshot observado | Patrón evaluado | Decisión |
|---|---|---|---|
| https://github.com/grokability/snipe-it | `8d285d254fcb03aaa2111872e19aaca6e1030c67` (observado 2026-09-10) | checkout/check-in, custodia, asset tags, historial, límites de alcance | **Estudiar/adaptar patrón. No copiar.** Licencia AGPL-3.0: mantener frontera legal clara. |
| https://github.com/allegro/ralph | `adbe619caba31425a6b28bd8913fed2500c2fd96` | lifecycle de activos/CMDB y back-office assets | Referencia fuerte para ciclo de vida futuro de activos. No instalar Ralph como base del producto. |
| https://github.com/glpi-project/glpi | `5b3eadfa0a549877559e08e6e5a13047c380aace` | activos/configuración, ubicación, incidencias/solicitudes | Estudiar separación activo/incidencia/configuración. No adoptar suite completa. |
| https://github.com/openboxes/openboxes | `635b225b0dfc0d07619dad1a6583fbd9d803d5f4` | inventario y movimientos de stock | Estudiar movimientos/ubicaciones para Control de Material y cierre de proyecto. No dependencia. |
| https://github.com/apache/casbin-node-casbin | `aad42ce2be70908bbc76c5b89b505cf0655245e8` | RBAC/ABAC/policy engine | No se integra en 0.1; RBAC propio es pequeño y auditable. Revaluar si las políticas crecen. |
| https://github.com/fastapi/full-stack-fastapi-template | `cb740b656d7a0a6c5e12c7bf8e50343ec94ee9c7` | arquitectura FastAPI/PostgreSQL, testing y separación web/API | Referencia de stack y prácticas; esta implementación se escribió específicamente para Server Oficina, sin copiar el template. |

## Infraestructura inventariada para futuro

Estas referencias ya estaban registradas en la biblioteca técnica y se mantienen como opciones, **no como componentes de la alpha**:

- https://github.com/tailscale/tailscale — acceso remoto privado futuro;
- https://github.com/juanfont/headscale — control plane self-hosted futuro;
- https://github.com/rclone/rclone — copias/exportaciones a destinos externos;
- https://github.com/syncthing/syncthing — archivos/datasets, explícitamente **no** DB viva;
- https://github.com/microsoft/playwright — E2E web cuando se cierre la UI física/LAN.

## Política de mantenimiento de referencias

Antes de tomar código de una referencia futura:

1. fijar commit/tag exacto;
2. revisar licencia vigente;
3. documentar archivos/patrones concretos que se pretenden adaptar;
4. justificar por qué aporta frente a implementación propia;
5. añadir pruebas de comportamiento;
6. registrar en CHANGELOG/NOTICE y este documento.
