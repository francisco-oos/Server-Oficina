# Protocolo de relevos — Server Oficina

## Objetivo

Trabajar Server Oficina por bloques verificables, de forma que ningún agente dependa de confiar ciegamente en el informe del agente anterior.

Cada relevo debe poder ser retomado por otra persona o agente sin contexto de conversación.

## Regla principal

Un relevo NO comienza implementando.

Primero debe:

1. leer este protocolo;
2. leer el `HANDOFF` anterior;
3. comprobar el commit/base declarado;
4. revisar `git status`;
5. ejecutar los gates PRE aplicables;
6. inspeccionar de nuevo el código modificado por el relevo anterior;
7. corregir cualquier regresión encontrada;
8. sólo entonces continuar con el bloque nuevo.

## Estructura obligatoria de cada relevo

Cada relevo debe dejar un archivo:

`docs/handoffs/HANDOFF_RXX_<tema>.md`

con:

- commit/base de entrada;
- objetivo del relevo;
- archivos modificados;
- decisiones tomadas;
- pruebas PRE;
- pruebas POST;
- hallazgos de segunda revisión;
- riesgos conocidos;
- pendientes deliberados;
- instrucciones exactas para el siguiente relevo.

## Evidencia mínima de cierre

No se acepta "funciona" sin evidencia.

Para código Python:

```text
python -m compileall -q app tests run.py
pytest -q
```

Para frontend, cuando Node esté disponible:

```text
node --check app/static/app.js
```

Para cambios visuales o de interacción:

- ejecutar recorrido de navegador;
- registrar qué recorridos se comprobaron;
- no sustituir un E2E bloqueado por un PASS ficticio.

## Segunda revisión obligatoria

Después de que las pruebas pasen, el mismo relevo debe volver a leer su diff buscando:

- lógica duplicada;
- permisos incorrectos;
- datos hardcodeados;
- pérdida de trazabilidad;
- acciones automáticas que deberían requerir decisión humana;
- errores de nomenclatura;
- comentarios/documentación desactualizados;
- cambios que mezclen persona, activo, nodo, vehículo u otros dominios como si fueran el mismo flujo.

## Filosofía de dominio

Server Oficina comparte un núcleo temporal/auditable, pero cada dominio conserva su semántica.

Ejemplos:

- Persona: identidad estable + relaciones laborales + asignaciones + asistencia + cursos + EPP + incidencias.
- Activo: identidad estable + identificadores + custodia + movimientos + mantenimiento + evidencia.
- Nodo: activo con capacidades de operación sísmica + TENDIDO/ROTACIÓN/LEVANTADO/RETORNO y excepciones.
- Vehículo: activo con flujo de transporte, conductor, checklist y evidencias.
- Taller: orden de trabajo, diagnóstico, intervención, piezas, resultado y downtime.

El `OperationalEvent` común no sustituye los historiales especializados.

## Producción vs desarrollo

La Latitude `server-oficina` no se considera únicamente un host de QA.

Tiene dos funciones que deben coexistir de forma explícita:

1. **Server Oficina de operación LAN**.
2. **Work/Compute Node autorizado**, utilizable por Aleyon o agentes para tareas de desarrollo, compilación, pruebas, revisión y ejecución controlada.

Las tareas de agentes nunca deben poder modificar datos operativos de producción sin un gate y autorización explícita.

El desarrollo cotidiano se valida primero en una computadora de desarrollo, con base SQLite aislada, antes de promover cambios a la Latitude.
