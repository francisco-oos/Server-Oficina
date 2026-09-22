# PRE — Server Oficina 0.2.0-alpha.1

## Base

- rama base: `main`
- commit autoritativo: `2d40e558aa8d5d09e7f783c9e97857233f10f18e`
- suite local reportada antes de la evolución: 66 pruebas aprobadas;
- versión base: 0.1.0-alpha.4.

## Objetivo

Añadir una capa local-first sin sustituir Tracking Core: sincronización LAN,
versiones documentales, procedencia, aprendizaje por aclaración y grafo
temporal. Synology queda como réplica; la IA como intérprete.

## Riesgos que el gate debe cubrir

- corrupción o pérdida por concurrencia;
- propagación accidental de borrado;
- mezcla de aprendizaje entre áreas;
- IA pública por mala configuración;
- lectura de temporales/archivos incompletos;
- divergencia SQLite/PostgreSQL;
- regresiones del dominio 0.1.

No se promueve a `main` ni a la Latitude productiva sólo por completar código.
