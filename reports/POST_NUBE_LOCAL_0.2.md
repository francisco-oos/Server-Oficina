# POST — Server Oficina 0.2.0-alpha.1 (candidato)

## Implementado

- documentos y DAG de versiones;
- peers/shares y políticas de borrado;
- leases cooperativos;
- detección de concurrencia por vectores;
- merge semántico 3-way;
- aprendizaje documental por preguntas y reglas aprobadas;
- hechos extraídos y grafo con procedencia;
- adaptadores fail-closed para Syncthing/LLM privados;
- watcher estable y worker;
- API de Nube Local;
- CI Python 3.12/3.13 y simulación ≥20 clientes.

## Hallazgo real del gate

La primera corrida de la simulación de 24 clientes detectó una diferencia de
semántica temporal entre SQLite y PostgreSQL: SQLite devolvía un datetime sin
zona y el lease lo comparaba contra UTC aware. El gate falló correctamente.
Se agregó normalización explícita a UTC en la frontera de lectura.

## Estado

Candidato de laboratorio, **no producción todavía**. El código no habilita
automáticamente peers, Synology ni LLM. El script
`scripts/preparar-nube-local-lab.sh` es dry-run por defecto.

Pendiente para promoción:
- gate CI final de la rama;
- prueba física Latitude + SSD;
- red LAN real;
- caída/reconexión NAS;
- restore/rollback;
- formatos anonimizados reales de cada área;
- cliente/companion de escritorio para convertir los leases en aviso de archivo
  abierto antes de escribir.
