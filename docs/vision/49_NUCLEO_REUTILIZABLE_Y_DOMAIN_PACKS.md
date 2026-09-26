# 49 · Visión — Core reutilizable y Domain Packs

## Observación

El núcleo de Server Oficina no necesita conocer de forma permanente que esta
oficina trabaja con nodos sísmicos, AFU, cabos, sismógrafos o determinados
formatos Excel. Esos conceptos pertenecen al perfil de operación actual.

Si sincronización, identidad, evidencia, versiones, grafo, consulta, auditoría
y almacenamiento permanecen genéricos, el mismo motor puede servir a oficinas
con dominios distintos.

## Separación objetivo

```text
SERVER OFICINA CORE
├─ usuarios / estaciones / sesiones
├─ sincronización / conflictos / versiones
├─ almacenamiento / Content Resolver
├─ documentos / evidencia / procedencia
├─ grafo temporal
├─ búsqueda / consulta / datasheets
├─ auditoría
└─ runtime de lectores/agentes
        +
DOMAIN PACK
├─ áreas
├─ vocabulario y aliases
├─ familias documentales
├─ schemas y mappings
├─ autoridad de fuentes
├─ estados y reglas
├─ widgets/vistas
└─ skills/prompts aprobados
```

## LLM

El modelo local es reemplazable. No se codifican en pesos ni en un prompt
monolítico las reglas particulares de una oficina. El conocimiento durable se
guarda como datos versionados: mappings, schemas, reglas, ejemplos aprobados y
autoridad de fuentes.

Por eso cambiar de modelo, actualizarlo o incluso operar temporalmente sin LLM
no elimina el conocimiento organizacional.

## Estado real

El **Core ya tiene varias piezas reutilizables**, pero el repositorio todavía
contiene módulos explícitos de Adquisición Sísmica (nodos, Material, Taller,
Transporte, RRHH, etc.). Por tanto, hoy no se declara producto universal.

La dirección es extraer progresivamente esas reglas a un Domain Pack sin
degradar el sistema que necesita esta oficina.

## Gobierno

- el Core nunca aprende silenciosamente reglas de negocio;
- un Domain Pack es versionable y auditable;
- reglas nuevas requieren fuente/área responsable;
- usuarios autorizados pueden consultar transversalmente documentos;
- owner_area define autoridad, no invisibilidad;
- un paquete puede desactivarse o reemplazarse sin perder archivos/evidencia;
- los tests del Core usan fixtures genéricas; los tests del dominio usan
  ejemplos sintéticos de su paquete.
