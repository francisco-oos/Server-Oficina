# 23 · Plan de pruebas y casos de uso alpha.3

## Criterio de entrega

No basta que la API arranque. Alpha.3 se entrega sólo si la suite reproduce historias operativas completas.

## Escenarios automáticos incluidos

### RRHH

- primer administrador sólo una vez;
- usuario con rol restringido;
- alta de persona;
- recontratación manteniendo el mismo `person_id`;
- categoría;
- licencia y vigencia;
- rotación 30/15 como dato configurable;
- proyecto/grupo/ubicación/supervisor/unidad;
- asistencia manual;
- preview/commit de asistencia;
- curso RRHH→HSE;
- renuncia;
- despido;
- caso sin sanción automática.

### Asset Core

- alta de nodo, radio, antena, teléfono, computadora, dron, vehículo, servidor y NAS;
- SERCEL, INOVA, DJI, GENERIC;
- tecnología futura agregada sin modificar Python;
- IMEI, QR, serie y número económico;
- custodia a persona;
- búsqueda por identificador;
- metadata adicional de importación preservada.

### Nodos

Secuencia:

```text
TENDIDO → ROTACION → LEVANTADO → RETORNO
```

Se verifica línea/estaca, participante, responsable, fecha y persistencia del movimiento previo.

Matriz de excepciones:

```text
DAMAGED
BURNED
MISSING
LOST
STOLEN
SEIZED
MAINTENANCE
HIBERNATED
NO_INFO
```

Se prueban además recuperación y deshibernación.

### Taller

- abrir orden;
- entrada automática a mantenimiento;
- pieza/serial retirado e instalado;
- observación SOH/RUL;
- confirmar que RUL NO cambia el estado por sí solo;
- diagnóstico/acción/cierre;
- retorno a AVAILABLE.

### Inventario

- crear corte;
- contar material encontrado;
- cerrar;
- listar faltante no contado;
- no declarar pérdida definitiva automáticamente.

### Evidencias

- repositorio LOCAL;
- upload en streaming >1 MiB + SHA-256/tamaño;
- repositorio SMB no montado devuelve 503;
- archivo existente puede indexarse sin moverlo;
- ruta manipulada (`../`) no puede indexar fuera del repositorio.

### Extensibilidad

- perfil personalizado: crear → editar permisos → asignar a usuario, manteniendo perfiles base protegidos;
- nuevo estado `QUARANTINED`;
- nuevo movimiento `CUARENTENA`;
- nuevo tipo `SMART_SENSOR_FUTURE` con capacidad `node_field`;
- nueva tecnología `TECH_X_FUTURE`;
- el sensor participa en reglas del Core sin cambio de código específico para su nombre.

## Gates

```text
BACKEND_OK
FRONTEND_CONTRACT_OK
FRONTEND_OK
DEPLOY_CONTRACT_OK
DEPLOY_OK
PACKAGE_OK
```

`VALIDAR_FRONTEND_E2E.sh` es gate separado porque requiere un Chromium/Chrome real. El recorrido E2E incluye primer admin, login, dashboard, alta de persona, alta de nodo, TENDIDO y logout.

## Historia de aceptación transversal

Además de pruebas unitarias/de dominio separadas, la suite ejecuta una historia integrada que registra una persona con categoría/licencia/rotación/asistencia/curso, le asigna unidad/radio/nodo, recorre TENDIDO→ROTACION→LEVANTADO→RETORNO, registra nodos quemado e incautado, abre/cierra mantenimiento con cambio de batería, realiza inventario con faltante, procesa renuncia y genera cierre auditable del proyecto. El objetivo es demostrar que los módulos comparten las mismas identidades y timelines.

## Cierre de proyecto

Se valida que el corte identifique material crítico y transferible, persista como snapshot y permanezca inmutable aunque un equipo sano sea transferido posteriormente al proyecto siguiente.

## Cobertura final de construcción

La suite final de alpha.3 contiene **27 pruebas automáticas aprobadas**. El detalle reproducible se mantiene en `reports/TEST_RESULTS.md`.
