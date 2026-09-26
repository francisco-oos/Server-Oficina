# ADR-048 — Almacenamiento jerárquico, resolver lógico y dominio desacoplado

- Estado: ACEPTADO PARA CANDIDATO 0.2
- Fecha: 2026-09-26

## Decisiones

1. Syncthing permanece como transporte de la capa HOT; no se introduce un
   segundo motor bidireccional sobre la misma carpeta.
2. Una versión documental se identifica por su identidad y hash; la ruta física
   es una ubicación reemplazable.
3. Se introducirá un Content Resolver con múltiples ubicaciones verificadas.
4. Los archivos pesados podrán ir directo a un endpoint NAS sin atravesar el SSD
   de la Latitude cuando la política lo permita.
5. El acceso transparente de largo plazo en Windows se diseñará sobre CFAPI/
   placeholders, no sobre archivos .url.
6. No existe umbral de tamaño hardcodeado: políticas de almacenamiento son
   configuración auditable.
7. La indisponibilidad nunca se oculta: placeholder sin origen/caché produce
   estado UNAVAILABLE claro.
8. La sesión digital de una PC complementa, pero no sustituye, RRHH.
9. Los documentos sincronizados son consultables transversalmente por usuarios
   autorizados; owner_area gobierna autoridad del dato, no invisibilidad.
10. El conocimiento específico de una oficina no se hardcodea en pesos/prompt
    del LLM. Se modela como Domain Pack/versiones de configuración.
11. El Core reusable debe poder ejecutar otros perfiles de oficina; el paquete
    actual de Adquisición Sísmica conserva sus módulos y vocabulario propios.

## Consecuencias

- Menos escritura y redundancia sobre la Latitude.
- NAS reemplazable sin alterar IDs documentales.
- Mayor complejidad del Companion Windows, porque placeholders requieren un sync
  provider real.
- Las pruebas deben incluir pérdida de NAS durante hidratación y caché.
- Se necesita catálogo de ubicaciones, políticas y verificación de réplicas
  antes de implementar subida directa de contenido real.
