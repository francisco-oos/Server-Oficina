# 10 · Roadmap incremental

## 0.1.0-alpha.2 — baseline físico

Oficina/Personal + Tracking Core, empaquetado, iniciadores y despliegue en Latitude. Esta es la release actualmente usada como baseline estable antes de actualizar.

## 0.1.0-alpha.3 — base operacional integrada

Incluye RRHH operativo ampliado, perfiles configurables, organizaciones, ubicaciones, Asset Core, identificadores, custodia, movimientos, Tracking Nodes, mantenimiento/partes/salud, inventario físico, cierre auditable de proyecto, evidencias NAS/SMB, tipos/tecnologías configurables, importación masiva de activos y UI profesional reorganizada.

### Criterio para promover alpha.3

No basta compilar. Debe pasar suite, contratos frontend/deploy, smoke HTTP, integridad de manifiesto y revisión de paquete. El navegador E2E se registra separadamente si el entorno de construcción lo bloquea.

## Próximas evoluciones después de alpha.3

- adaptadores SERCEL/INOVA/Tendido Diario con reglas versionadas y conciliación de fuentes;
- integración NodeHealth como fuente estructurada de health observations;
- HSE: PDF/JSON cifrado/QR/fotos conservando original;
- Transporte: checklist, km, combustible y evidencias;
- captura de campo offline/store-and-forward;
- reglas más ricas de documentos/vigencias y reportes;
- migraciones versionadas cuando aparezcan cambios destructivos/ALTER.

## Principio permanente

No abrir cinco módulos incompletos a la vez. Cada bloque debe mantener identidad, procedencia, historial, permisos, pruebas y documentación antes de darse por cerrado.
