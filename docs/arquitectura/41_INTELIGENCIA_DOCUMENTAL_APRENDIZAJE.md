# 41 · Inteligencia documental y aprendizaje operativo

## Regla

> El LLM interpreta; Server Oficina recuerda.

No se reentrena un modelo cada vez que mueven una columna. El conocimiento
estable vive en reglas, esquemas y correcciones aprobadas.

## Pipeline

```text
archivo estable
→ versión + SHA-256
→ diff / estructura
→ extractor determinista
→ reglas aprendidas
→ ¿ambigüedad?
    no → staged facts
    sí → IA local / pregunta humana → regla aprobada
→ validación de autoridad
→ Tracking Core / BD
```

## Prioridad

1. JSON embebido de aplicaciones propias.
2. CSV/XLSX con esquema conocido.
3. reglas aprobadas.
4. conversión documental local.
5. LLM local para ambigüedad/texto libre.
6. revisión humana.

## Conversación de enseñanza

```text
Server Oficina:
Detecté una columna nueva: VIG. M.D.
¿Corresponde a training.expiration_date?

Seguridad:
Sí.

Server Oficina:
Regla guardada para HSE / DRIVER_TRAINING.
```

La regla queda limitada por área + familia + etiqueta + contexto.

## PREVIEW y automatización

Interpretaciones nuevas o ambiguas siguen PREVIEW/revisión. Una regla humana ya
aprobada puede reproducirse automáticamente cuando identidad, autoridad y
validadores son inequívocos. Eso no es “decisión nueva de IA”.

## IA local

El adaptador previsto usa un endpoint local compatible con llama.cpp y JSON
Schema. URLs públicas se rechazan por defecto. El modelo concreto se decide
después de benchmark en la Latitude; no se descarga automáticamente.

## Asistente

El chat consulta primero BD/grafo. Ante “R-058 llegó dañado; busca historial”
devuelve cronología + evidencias y límites de lo sabido, nunca una acusación.
