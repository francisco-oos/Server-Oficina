> **Nota (0.1.0-alpha.4).** La arquitectura de interfaz vigente está en
> `docs/31_ARQUITECTURA_UI_Y_NAVEGACION.md`. Este documento se conserva como
> antecedente de los criterios de flujo que la motivaron.

# 26 · UI profesional y flujos

## Objetivo

La UI alpha.2 demostraba funcionalidad, pero no la organización final. Alpha.3 introduce navegación por dominio:

```text
OPERACIÓN
  Dashboard
  Localizar
  Activos y Nodos
  Tracking Nodes
  Taller / Mantenimiento
  Inventario físico
  Evidencias

OFICINA
  Personal
  Asistencia
  Importaciones
  EPP
  Capacitación
  Casos

ADMINISTRACIÓN
  Proyectos y ubicaciones
  Perfiles y permisos
  Catálogos
  Usuarios
  Auditoría
```

## Principios

- búsqueda primero;
- estado actual visible pero siempre acompañado de timeline;
- formularios cortos para operación repetitiva;
- catálogos administrables sin editar código;
- errores de FastAPI legibles (no `[object Object]`);
- sin CDN ni dependencia web externa para operar en campamento;
- responsive para PC/tableta/teléfono.

## Localizador

Busca simultáneamente personal y activos por:

- nombre / ID laboral;
- código interno;
- serie;
- IMEI;
- QR;
- número económico;
- identificadores futuros.

La respuesta de persona incluye contexto operacional y activos en custodia. La respuesta de activo incluye estado y último movimiento.

## Ficha de activo

Debe permitir revisar en una sola vista:

- identidad/tecnología/identificadores;
- estado actual;
- proyecto/grupo/ubicación/custodio;
- historial de movimientos;
- línea/estaca;
- mantenimiento;
- salud/RUL;
- evidencias.

## Evolución posterior

- mapas/croquis cuando exista georreferenciación confiable;
- operación por lotes con selección masiva visual;
- dashboards específicos por rol;
- lector QR/cámara móvil;
- vistas especializadas para transporte/HSE sin romper Asset Core.

## Configuración sin código

La vista Catálogos permite crear vocabularios, tipos de activo con capacidades y tecnologías. Proyectos/Ubicaciones administra localizaciones sin asumir campamentos predefinidos. Perfiles y permisos permite crear perfiles de negocio sin editar Python.

## Evidencias existentes

La UI de Evidencias tiene dos caminos: subir y almacenar, o **indexar un archivo ya existente** mediante una ruta relativa en el repositorio. El segundo camino mantiene intacto el archivo que un usuario copió desde Windows/Organizador.

## Corte de proyecto

Proyectos ofrece vista previa del cierre de material (estados, excepciones críticas y transferibles) y creación explícita del corte auditable. Cerrar no mueve ni da de baja equipos automáticamente.
