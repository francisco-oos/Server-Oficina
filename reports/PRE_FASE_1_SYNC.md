# PRE — Fase 1 · Sincronización

Base: 36b4e581edf5220a78a006d96fbab009d9207022
Rama: agent/openai/sync-core-v0.2

## Decisión

Se congela temporalmente el trabajo de LLM/Document Intelligence. Primero se cierra el transporte PCs ↔ Latitude y el comportamiento de archivos compartidos.

## Base reutilizada

- SyncPeer / SyncShare / SyncPeerShare;
- DocumentRecord / DocumentVersion;
- watcher estable;
- tombstones;
- leases;
- vector clocks;
- merge semántico;
- adaptador REST básico de Syncthing.

## Este incremento

- contrato de topología LAN-only;
- configuración determinista de devices/folders;
- cliente REST de Syncthing ampliado;
- pruebas del contrato REST y de la topología.

## Fuera de alcance de este corte

- Synology;
- companion Windows;
- IA local;
- extractores por área;
- archivos reales.