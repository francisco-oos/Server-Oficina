# Reporte de cambios de interfaz

## El error que se corrige

> Interpretar «todo tiene trazabilidad» como «todo debe tener la misma
> interfaz».

Tracking Core es común por debajo, pero RRHH sigue la vida laboral de una
persona, Operación el ciclo de un nodo, Material la custodia, Transporte las
unidades y Taller el diagnóstico. Sus fichas, acciones, estados y timelines
**no son intercambiables**.

## Navegación

### Antes

```
OPERACIÓN        Dashboard · Localizar · Activos y Nodos · Tracking Nodes ·
                 Taller · Inventario · Evidencias
OFICINA          Personal · Asistencia · Importaciones · EPP · Capacitación · Casos
ADMINISTRACIÓN   Proyectos · Perfiles · Catálogos · Usuarios · Auditoría
```

Fija en `index.html`, idéntica para todos, visible aunque el perfil no tuviera
permiso (y entonces la vista fallaba con 403 al pulsarla).

### Ahora

```
RESUMEN                 Vista resumen
RECURSOS HUMANOS        Personal · Asistencia · EPP · Importaciones
SEGURIDAD / HSE         Capacitación · Incidencias y casos
TRANSPORTE              Unidades · Checklist · Incidencias de unidad
CONTROL DE MATERIAL     Activos · Inventario · Evidencias · Cierre de proyecto
OPERACIÓN · NODOS       Tracking Nodes
TALLER / TX             Órdenes de taller
ADMINISTRACIÓN          Proyectos · Perfiles · Autoridad del dato · Catálogos ·
                        Usuarios · Modo DEV · Auditoría
```

Construida en JavaScript desde una tabla declarativa, **filtrada por permisos**.
Las áreas del usuario se marcan «tu área» sin ocultar el resto: el sistema es
compartido por diseño.

### Búsqueda transversal

Nueva, siempre visible en la cabecera. Localiza persona, nodo, radio, teléfono,
unidad, IMEI, QR, serie o número económico y **abre la ficha que corresponde**.
Cada resultado indica su tipo, su estado y **por qué coincidió**. Lo que el
usuario no podría abrir se omite, pero se informa cuántas coincidencias se
ocultaron, para que pueda pedir acceso en lugar de creer que no existen.

## Vista resumen

### Antes

Siete contadores fijos (`activos`, `EPP`, `casos`, `capacitación`, `activos
totales`, `críticos`, `taller`), un desglose por estado y una lista de eventos.
Hardcodeados en el endpoint.

### Ahora

Siete vistas resumen configurables (general + una por área), 28 widgets
disponibles y un modo DEV completo. La composición es un dato del operador, no
código.

Responde las cinco preguntas del encargo:

| Pregunta | Cómo |
|---|---|
| ¿Qué está pasando? | métricas de estado por área |
| ¿Qué requiere atención? | widgets de excepción con acento rojo |
| ¿Qué cambió? | altas, bajas y actividad reciente |
| ¿Qué está pendiente? | EPP, cursos, órdenes, inventarios |
| **¿Qué debo atender yo?** | widget `general_mis_pendientes`, que sólo lista lo que **este** usuario puede resolver |

El último es el que evita que la pantalla sea ruido.

## Fichas por dominio

### Persona · expediente de vida laboral

Bloque de **Localización** al frente, con los campos exactos que pide el
encargo: Estado · Grupo · Responsable/supervisor · Unidad · Conductor · Radio ·
Teléfono · Ubicación/campamento · Proyecto (más ID laboral, puesto y categoría).

Cada contratación es un bloque propio con sus contratos, renovaciones y eventos
laborales, porque **persona ≠ contratación**: una recontratación es una relación
nueva sobre la misma identidad, y el expediente lo muestra.

Pestañas: Historia laboral · Asignaciones · Asistencia · Cursos · EPP · Activos
entregados · Casos · Nodos relacionados · Evidencias · Historial completo.

Los activos aparecen como **entregados**, no como custodia de almacén: es el
hecho relevante desde RRHH. Los nodos con excepción en los que la persona figura
como responsable se muestran etiquetados como trazabilidad, **no** como
imputación.

### Nodo · ciclo operacional

Ya no se reduce a un campo `estado`. La ficha abre con **Situación actual** y su
derivación explícita:

```
Estado          DAMAGED
Último movimiento  DAMAGE       Ocurrió  14/09 15:02
Línea  L-1200    Estaca  1010
Quien lo manejaba  Operador Nodo Díaz
```

Las excepciones se separan en un panel propio con acento rojo. Pestañas:
Operaciones y lotes · Movimientos · Custodia · Taller · Salud/RUL · Inventarios ·
Evidencias · Historial.

### Activo genérico

Identidad con todos sus identificadores, custodia y entregas, movimientos,
inventarios, mantenimiento, salud y evidencias. **Sin** secciones de operación
de campo, que no le corresponden a un radio ni a una computadora.

### Unidad de transporte

Abre con la **asignación vigente** —conductor, grupo, proyecto, radio, teléfono,
disponibilidad—, no con su ficha de almacén. Incidencias abiertas destacadas
arriba. Formularios contextuales de asignación, checklist y reporte de
incidencia, cada uno visible sólo con su permiso.

## Lo que dejó de ser una tabla CRUD

| Vista | Antes | Ahora |
|---|---|---|
| Dashboard | contadores fijos | widgets configurables con enlaces |
| Personal | tabla + formulario | tabla + expediente completo |
| Nodos | tabla de activos | métricas por estado + registro de operación + ciclo por nodo |
| Taller | tabla de órdenes | órdenes abiertas como tarjetas accionables + historial |
| Inventario | tabla de sesiones | sesiones + detalle con faltantes destacados |
| Transporte | no existía | métricas de flota + tabla con vínculos resueltos + ficha |
| Cierre de proyecto | panel embebido | vista propia con vista previa antes de cerrar |
| Autoridad del dato | no existía | matriz de gobierno |
| Modo DEV | no existía | configurador completo |

## Avisos y prevención de errores

- Los datos no capturados se muestran como **«No capturado»** en cursiva, para
  distinguirlos de un valor vacío real. Saber qué falta es información útil.
- Las acciones destructivas o irreversibles piden confirmación explicando qué
  hacen **y qué no hacen**: «Esta acción NO mueve ni da de baja activos».
- Las notas de regla aparecen donde se necesitan: «un faltante de inventario no
  es una pérdida definitiva», «un checklist con falla no inmoviliza la unidad»,
  «una observación SOH/RUL nunca da de baja un equipo».
- Los errores estructurados de FastAPI se traducen a texto legible; la
  regresión `[object Object]` está cubierta por el gate de contrato.

## Responsive

| Ancho | Comportamiento |
|---|---|
| > 1100 px | barra lateral fija, rejilla de 12 columnas |
| 860–1100 px | widgets más anchos |
| < 860 px | barra lateral como panel deslizante con botón ☰ y velo |
| < 560 px | una columna, formularios apilados |

Verificado por E2E a 390 px: sin desbordamiento horizontal y el panel se cierra
solo al navegar. Áreas de toque de 34–38 px mínimo, pensadas para operar con
guantes.

## Legibilidad del código de interfaz

`app.js` pasó de 170 líneas ilegibles —vistas completas de 3 000 caracteres en
una sola línea— a 2 450 líneas estructuradas y comentadas en español, con
secciones claras y funciones con una responsabilidad cada una. Era un requisito
del trabajo multidesarrollador, no cosmética.

## Lo que NO se hizo

No se eliminó comportamiento válido para simplificar. Todas las vistas de
alpha.3 siguen existiendo, con sus mismos endpoints; lo que cambió es cómo se
presentan y desde dónde se llega a ellas.
