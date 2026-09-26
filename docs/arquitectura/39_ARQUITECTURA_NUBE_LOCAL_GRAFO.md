# 39 · Arquitectura — Nube Local, grafo temporal y contexto verificable

## Vista general

```text
PC RRHH ───────┐
PC HSE ────────┤
PC Transporte ─┤     LAN / sincronización local-first
PC Material ───┤
PC Taller ──────┘
                 ▼
        Dell Latitude 7220 + SSD
        ├─ Syncthing (motor de réplica)
        ├─ Registry de documentos/versiones
        ├─ Document Intelligence
        ├─ Tracking/Reconciliation Core
        ├─ PostgreSQL
        ├─ Grafo temporal derivado
        ├─ FastAPI + Dashboard/Buscadores
        └─ Adaptador NAS
                 │
                 ▼ cuando está disponible
             Synology
```

## Dos planos deliberadamente separados

### Plano de archivos

Se ocupa de bytes y versiones: carpeta por área, réplica LAN, detección estable,
hashes, historial, conflictos y réplica NAS.

### Plano de conocimiento

Se ocupa de significado: identidad, eventos, custodia, ubicación,
cursos/licencias, hechos extraídos, autoridad y procedencia.

Un error de IA no puede modificar el archivo canónico. Un fallo de
sincronización no inventa un hecho.

## Topología

La primera producción usa **hub-and-spoke**: cada PC sincroniza con
`server-oficina`; no se crea full mesh. Synology es una réplica separada.

## Grafo temporal

No se introduce otra base de grafos. PostgreSQL conserva dominio y
`extracted_facts` representa aristas documentales con sujeto, predicado,
objeto/valor, área, tiempo, confianza y versión fuente.

El grafo se usa para navegar y para el asistente. Puede reconstruirse; nunca
reemplaza `AssetMovement`, `AssetCustody`, `TrainingRecord`, etc.

## Componentes incorporados en 0.2.0-alpha.1

- peers/shares de sincronización;
- documentos y DAG de versiones;
- aprendizaje y aclaraciones;
- hechos extraídos/grafo;
- leases y conflictos;
- merge semántico 3-way;
- adaptadores privados Syncthing/LLM;
- API `/api/local-cloud/*`;
- watcher estable de dos pasadas.

## Diferido deliberadamente

No se fija modelo LLM, no se descargan pesos, no se fusionan bytes XLSX, no se
instala Apache AGE ni se modifica configuración de Syncthing automáticamente.
Primero se valida el núcleo con la Latitude y formatos reales.
