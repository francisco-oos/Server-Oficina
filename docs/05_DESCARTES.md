# 05 · Descartes y límites actuales

Un descarte no significa "malo"; significa que no resuelve mejor el alcance actual.

## No usar Snipe-IT/GLPI/Ralph/OpenBoxes como producto base

Cubren partes del problema, pero el dominio real contiene plantado/levantado/rotado, TX, Taller, HSE, proyectos sísmicos, identidad laboral/recontratación y conciliación entre fuentes. Forzar la operación a su esquema trasladaría la complejidad a plugins/customizaciones y haría al proyecto dependiente de decisiones ajenas.

**Conservado:** patrones de ciclo de vida, check-in/out, movimientos, incidentes y custodia.

## No Neo4j en la primera versión

Conceptualmente el sistema es un grafo temporal, pero PostgreSQL cubre el volumen y evita otra base/backup/operación. Si consultas transversales futuras demuestran un cuello de botella, se podrá añadir una proyección de grafo sin reemplazar la fuente de verdad.

## No microservicios desde el inicio

Se adopta monolito modular. Extraer un módulo será una optimización futura basada en carga/aislamiento real.

## No React/Vite para 0.1

El objetivo inmediato es poner un dashboard real en LAN mientras se prepara la tablet. HTML/CSS/JS simple reduce toolchain y consumo. La API desacoplada deja abierta una UI React posterior.

## No sanciones o scoring automático de personas

El sistema puede calcular frecuencias y mostrar eventos, pero una alta cantidad de reportes puede significar conducta preventiva, no un problema. La valoración laboral pertenece al área competente.

## No fusión automática de personas por nombre

Una coincidencia ambigua se convierte en `ImportIssue`. La identidad estable no se crea con heurísticas silenciosas.

## No sincronización de DB viva mediante Syncthing

Se permiten backups/exportaciones de archivos, no replicación ingenua de PostgreSQL/SQLite en ejecución.

## No integrar HSE completo todavía

Se conserva el contrato conceptual PDF + JSON cifrado + hash + fuente. La app existente sigue siendo una fuente futura; no debe bloquear la entrega de Oficina.
