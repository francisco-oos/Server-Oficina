# ADR-043 — Nube local, grafo temporal e IA documental

- Estado: **ACEPTADO PARA CANDIDATO 0.2**
- Fecha: 2026-09-21
- Rama: `agent/openai/local-cloud-graph-v0.2`

## Decisiones

1. documentos canónicos;
2. PostgreSQL como proyección temporal/auditable;
3. grafo derivado;
4. Syncthing como transporte LAN, no dominio;
5. topología estrella;
6. Synology como réplica;
7. lease cooperativo;
8. merge 3-way posterior a conflicto;
9. no merge binario de XLSX;
10. IA local fail-closed;
11. aprendizaje por reglas antes que fine-tuning;
12. n8n opcional, nunca autoridad;
13. Apache AGE diferido.

## Revisión del contrato de ingesta

La confirmación humana sigue obligatoria ante interpretación nueva. Una plantilla
ya aprobada puede aplicar hechos deterministas según política. La decisión
humana se vuelve regla reusable: no se pregunta lo mismo todos los días.

## Consecuencias

Menos tecnología nueva para el usuario y más responsabilidad interna de
versionado/procedencia. Una caída de IA no detiene archivos; una caída de NAS no
detiene LAN; cambiar de modelo no borra memoria; conflictos y borrado son
explícitos.
