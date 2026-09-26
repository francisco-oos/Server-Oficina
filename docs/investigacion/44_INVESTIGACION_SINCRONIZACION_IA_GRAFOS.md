# 44 · Investigación — sincronización robusta, merges, local-first, IA y grafos

Fecha de corte: 2026-09-21.

| Proyecto / técnica | Revisión | Aporte | Decisión |
|---|---|---|---|
| Syncthing | bb19c017 | bloques SHA-256, version vectors, conflictos, API | transporte LAN |
| Unison | 8772d26 | archivos de estado y topología estrella | patrón conceptual |
| rsync | algoritmo publicado | rolling + strong checksum | referencia |
| Git | modelo/merge-base | DAG, ancestro común, 3-way | adaptar |
| restic | diseño CAS | snapshots, hash, atomicidad, CDC | referencia de versiones |
| Kopia | CAS | dedupe/manifests/snapshots | backup futuro |
| Automerge | CRDT local-first | convergencia estructurada | módulos nativos futuros |
| llama.cpp | c550d2f | IA local + JSON Schema | candidato IA |
| Docling | b078ea3 | extracción documental | benchmark |
| MarkItDown | b8f79c5 | conversión ligera | fallback |
| n8n | 32aa462 | workflows | opcional |
| Apache AGE | fa109ef | Cypher/PostgreSQL | diferido |
| Organizador-Geografico-Evidencias | 94890f4 | copia segura/reconciliación | invariantes internas |

## Decisiones derivadas

Syncthing ya resuelve la capa difícil de réplica por bloques y versiones; se
añade identidad de usuario, área, lease, trazabilidad y merge semántico.
Unison refuerza el hub-and-spoke. Git inspira BASE/LEFT/RIGHT, pero se fusionan
registros, no bytes XLSX. Restic/Kopia inspiran inmutabilidad, contenido por hash
y atomicidad; no se crea CAS propio todavía. CRDT es valioso cuando Server
Oficina sea dueño del dato nativo, no para transformar mágicamente documentos
Office externos.

Apache AGE se evaluará sólo si el corpus real demuestra que BFS/SQL temporal es
insuficiente.

```text
bytes       → Syncthing / SMB / SSD
versiones   → DocumentVersion
significado → extractores + reglas + IA
hechos      → ExtractedFact / Tracking Core
estado      → dominio + autoridad
navegación  → grafo derivado
respaldo    → Synology
```
