# 13 · Investigación: RRHH operativo aplicado a Server Oficina

## Alcance

Server Oficina no intenta sustituir nómina/ERP corporativo. El alcance es **RRHH operativo de proyecto/campo**: identidad, relación laboral, proveedor/outsourcing, proyecto, grupo, asistencia, EPP, capacitación, evidencias y trazabilidad temporal.

## Fuentes estudiadas

- HR Open Standards — vocabularios/esquemas abiertos para intercambio de datos HR: https://www.hropenstandards.org/standards-downloads
- JEDx Worker API / Organizations API (finalizado 2024): https://www.hropenstandards.org/jedx-open-api-specifications
- HR Open Employment/Earnings: separación semántica entre datos del trabajador y registros de empleo.
- STPS — presentación de listas de constancias o competencias laborales / SIRCE: contexto para planes, cursos y constancias; Server Oficina no afirma sustituir el trámite oficial: https://www.gob.mx/stps/acciones-y-programas/stps-04-002-presentacion-de-listas-de-constancias-o-de-competencias-laborales
- NOM-017-STPS-2024: selección, uso y manejo de EPP, incluyendo revisión, reposición, mantenimiento, resguardo y disposición final: https://dof.gob.mx/normasOficiales/9496/stps/stps.html
- prototipo previo de Panel RRHH del proyecto: búsqueda por clave/nombre, ficha integral, jerarquía, asistencia, EPP y capacitación. Se rescata la intención UX, **no sus datos demo incrustados**.

## Decisiones confirmadas

### 1. Persona y empleo son entidades distintas

`persons.id` representa a la persona estable. Una baja y posterior recontratación genera otro `employment_engagement`, incluso si cambia el ID/clave laboral o proveedor.

### 2. Renovación de outsourcing no duplica persona

Las renovaciones mensuales/periódicas pertenecen a `contract_periods` relacionados con el engagement. No deben crear personas nuevas.

### 3. Proyecto, grupo y jerarquía son temporales

No guardar “grupo actual” o “jefe actual” como si fueran identidad permanente. Se deben conservar periodos para poder reconstruir una fecha pasada.

### 4. Estado operacional ≠ estado laboral

`ACTIVO/BAJA` laboral y `TRABAJO/DESCANSO/CAMPO/OFICINA` operacional son conceptos distintos. La futura programación de grupos/quincenas/turnos deberá modelarse en periodos de roster, no sobreescribir `Person.active`.

### 5. Capacitación necesita vigencia verificable

No todos los cursos vencen, pero cuando exista una vigencia operacional debe registrarse como dato explícito y con fuente. Próxima evolución:

```text
training_courses.validity_days / validity_rule
training_records.completed_at
training_records.valid_until
training_records.evidence_id
```

La UI debe mostrar vigente / por vencer / vencido, sin inferir una prohibición laboral automática salvo regla autorizada por el área competente.

### 6. EPP es workflow humano y evidencia

La alpha conserva solicitud → validación RRHH → historial oficial. La investigación de NOM-017 refuerza que el futuro EPP debe poder documentar selección, entrega, revisión, reposición, mantenimiento/resguardo y disposición según aplique. EPP serializado podrá enlazarse con Asset Core; consumibles no deben forzarse a ser activos serializados.

### 7. Casos no son scoring laboral

Los casos registran hechos/evidencia; la resolución pertenece a un humano autorizado. No habrá “índice de buen/mal empleado”, sanción automática ni IA que decida medidas disciplinarias.


## Aplicación práctica de la investigación HR Open / STPS

La referencia JEDx se usa para contrastar vocabulario e interoperabilidad, **no para copiar su esquema ni convertir Server Oficina en un HRIS genérico**. La separación entre persona, organización, trabajo/engagement y registros derivados coincide con el acuerdo del proyecto y reduce el acoplamiento a una sola empresa o outsourcing.

Para capacitación, el sistema debe distinguir al menos: catálogo del curso, programación, participación, resultado/completado, constancia/evidencia y vigencia operacional cuando aplique. Los datos necesarios para una salida administrativa futura se conservan con procedencia, pero cualquier envío oficial a SIRCE queda fuera de alcance hasta que RRHH lo autorice y se valide legal/operativamente.

Para asistencia y rotaciones, la fuente original (archivo, captura o integración) no se reemplaza silenciosamente. Una corrección posterior debe ser una corrección auditada, no una reescritura invisible del histórico.

## Próximas estructuras RRHH sin romper 0.1

Planeadas para el endurecimiento 0.2, después de validar datos reales:

```text
roster_periods / duty_periods      trabajo-descanso y grupos quincenales
supervision_assignments           responsable/supervisor temporal
training validity                 vigencia y evidencia
employment documents              sólo documentos necesarios y con control de acceso
import_issue_resolution           resolver rehire/homónimos desde UI
person operational snapshot       vista derivada, no tabla que borre historia
```

## Ficha integral deseada

La búsqueda por nombre/ID debe reunir, con permisos:

```text
persona estable
relación laboral vigente + histórico
proveedor/outsourcing
proyecto
puesto/categoría
grupo/cuadrilla
responsable temporal
asistencia/turno
EPP
cursos vigentes
casos/evidencia autorizados
activos en custodia (cuando exista Asset Core)
unidad/radio/teléfono/campamento (cuando existan módulos respectivos)
timeline
```

La ficha es una **vista de relaciones**, no una tabla duplicada con todos esos campos.

## Privacidad por diseño

- mínimo dato necesario para operación;
- permisos por función;
- auditoría de cambios;
- evidencia con procedencia;
- datos sensibles sólo cuando exista finalidad y autorización clara;
- exportaciones controladas;
- no publicar listados de personal en servicios públicos para “sincronizar”.
