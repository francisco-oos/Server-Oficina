# 03 · Decisiones y razonamiento

Este documento se mantiene separado de `01_PROBLEMA_Y_FINALIDAD.md`: aquí se registra **por qué** se eligió o descartó una alternativa, para que mantenimiento futuro pueda revisar supuestos.

## ADR-001 · PostgreSQL como fuente de verdad

**Decisión:** PostgreSQL en la tablet/servidor. SQLite se conserva sólo para pruebas, clientes offline futuros o herramientas locales.

**Razón:** múltiples usuarios/fuentes y crecimiento por áreas requieren concurrencia, integridad y consultas relacionales más robustas. La primera alpha se prueba contra SQLite aislado para velocidad, pero el instalador despliega PostgreSQL.

## ADR-002 · FastAPI/Python para el Core

**Decisión actual:** FastAPI + SQLAlchemy.

**Razón:** las fuentes operativas existentes de Tendido/NodeHealth/Supervisión Manager ya tienen una parte importante del tratamiento de CSV/XLSX/JSON en Python. La API queda tipada y la UI inicial no necesita un build frontend pesado.

**Alternativa estudiada:** Node/Express por experiencia de EventStudio. Se rescatan sus patrones de seguridad/pruebas, pero no su dominio ni su base de código. Si en el futuro el frontend requiere React, podrá consumir la misma API.

## ADR-003 · Monolito modular, no microservicios

**Razón:** la Latitude es un host limitado y el proyecto comienza con un área. Microservicios añadirían despliegues, redes, observabilidad y fallos distribuidos sin beneficio inmediato.

## ADR-004 · Sesiones opacas en BD, no JWT como requisito

Los tokens aleatorios se almacenan hasheados y son revocables. Para un servidor LAN administrativo es preferible poder invalidar sesiones inmediatamente. No se descarta OAuth/SSO futuro.

## ADR-005 · Scrypt estándar de Python

Se utiliza `hashlib.scrypt` para contraseñas y se evita añadir una dependencia criptográfica sólo para hashing. Parámetros y esquema quedan versionados en el hash almacenado.

## ADR-006 · Preview antes de importación

Un archivo cargado se conserva con SHA-256 y se procesa a un staging. **No modifica expedientes hasta confirmar**. Coincidencias ambiguas generan issue; no se fusionan personas por adivinación.

## ADR-007 · No reescribir los Excel actuales de entrada en la primera fase

Se construyen adaptadores a encabezados conocidos (`CLAVE`, `NOMBRE`, `PUESTO`, `GRUPO`, fechas). A futuro se podrá estandarizar la plantilla, pero el primer producto debe adaptarse a la operación existente.

## ADR-008 · Eventos + estado, no sólo `status`

El valor actual nunca sustituye la historia. El futuro tracking de nodos necesita saber cuántas reparaciones, piezas, custodias y transiciones existieron.

## ADR-009 · Permisos desde la primera versión

Aunque sólo esté terminado Oficina, el Core incluye RBAC granular. Ejemplo obligatorio: `epp.request` no implica `epp.validate_hr`.

## ADR-010 · Evidencia y decisión separadas

Una captura que muestra consumo de datos, una nota o un reporte no equivale a una sanción. El área reporta; RRHH/jefatura competente resuelve.

## ADR-011 · Referencias externas = estudiar/adaptar, no copiar

Los repositorios inventariados se usan para identificar patrones. No se incorpora código de Snipe-IT, Ralph, GLPI, OpenBoxes, Casbin ni otros sistemas salvo declaración futura explícita de licencia/procedencia. El producto se adapta al flujo real de Adquisición, no al revés.
