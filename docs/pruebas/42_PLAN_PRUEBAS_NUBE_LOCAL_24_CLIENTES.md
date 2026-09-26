# 42 · Plan de pruebas — Nube Local y Document Intelligence

## Gate automático

Debe pasar suite histórica + sintaxis +:
- traversal rechazado;
- relojes vectoriales;
- merge 3-way;
- conflicto mismo campo;
- 24 clientes;
- leases;
- aprendizaje VIG. M.D. y RESP.;
- aislamiento por área;
- grafo con procedencia;
- endpoints públicos LLM/Syncthing rechazados;
- watcher ignorando temporales de Office/Syncthing.

## Simulación 24 clientes

1. 24 PCs reservan 24 archivos distintos.
2. segundo escritor del mismo archivo es bloqueado.
3. 24 vectores independientes producen 276 pares concurrentes.
4. edits offline en campos distintos se combinan.
5. edits al mismo campo crean conflicto.

## Prueba física en Latitude

Sólo en share LAB:
1. medir SSD/RAM/CPU;
2. emparejar una laptop;
3. limitar Syncthing a LAN;
4. copiar 100 archivos;
5. modificar 20 y reconectar;
6. provocar conflicto;
7. revisar versiones;
8. registrar hashes/versiones;
9. simular NAS ausente;
10. reconectar NAS;
11. restaurar una versión;
12. verificar dashboard durante caída.

## Promoción

0.2.0-alpha.1 sigue siendo candidato. No va a main hasta CI verde, prueba
física, rollback/restore, medición de recursos, permisos y formatos reales
anonimizados por área.
