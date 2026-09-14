# 31 · Arquitectura de interfaz y navegación

## Principio rector

> Tracking Core es común por debajo, pero la experiencia de cada dominio debe
> reflejar su realidad. Las fichas, acciones, estados y timelines **no son
> intercambiables**.

El error que esta versión corrige es haber interpretado «todo tiene
trazabilidad» como «todo debe tener la misma interfaz».

## Tecnología

Página única sin framework ni dependencias remotas. El servidor vive en LAN y
puede no tener salida a Internet: una fuente o script en CDN dejaría la
interfaz en blanco. El gate `scripts/check-frontend-contract.py` falla si
aparece cualquier recurso remoto.

```
app/static/index.html   esqueleto y contenedores
app/static/app.js       navegación, vistas y fichas
app/static/styles.css   sistema visual y responsive
```

## Navegación doble

Ambas son necesarias; ninguna sustituye a la otra.

### Por área (barra lateral)

Se construye en `buildNav()` a partir de la tabla declarativa `NAV`, filtrando
por los permisos del usuario. Una entrada sin permiso **no se dibuja**: mostrar
opciones que después dan 403 es maltratar al operador de campo.

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

Las áreas propias del usuario se marcan («tu área») sin ocultar el resto: el
sistema es compartido por diseño.

### Transversal (buscador de cabecera)

Siempre visible. Buscar `123456` localiza persona, nodo, radio, teléfono,
unidad, IMEI, QR, serie o número económico, y **dirige a la ficha adecuada**.

Cada resultado indica su tipo de ficha (`dossier`), su estado y **por qué
coincidió** (`matched_on`), que es lo que el operador necesita para saber si
encontró lo que buscaba. Los resultados que el usuario no podría abrir se
omiten, pero se informa cuántos fueron: saber que existe algo fuera de su
alcance le permite pedir acceso en lugar de creer que no existe.

## Las cuatro fichas

No hay ficha universal. `GET /api/dossier/asset/{id}` devuelve `kind` y la
interfaz elige plantilla.

| Ficha | Función | Secciones propias |
|---|---|---|
| Persona | `person()` | localización · datos laborales · historia laboral · asignaciones · asistencia · cursos · EPP · activos entregados · casos · nodos relacionados · evidencias · historial |
| Nodo | `node()` | **situación actual con su derivación** · operaciones y lotes · excepciones · movimientos · custodia · taller · salud/RUL · inventarios · evidencias · historial |
| Activo | `asset()` | identidad · custodia y entregas · movimientos · inventarios · mantenimiento · salud · evidencias · historial |
| Unidad | `transportUnit()` | **asignación vigente** · incidencias abiertas · historial de asignaciones · checklist · incidencias · mantenimiento · movimientos · evidencias · historial |

Diferencias deliberadas, verificadas por `test_dossier_structures_differ_per_domain`:

- la persona tiene **vida laboral**; ningún activo la tiene;
- el nodo tiene **ciclo operacional**; el radio y la unidad no;
- la unidad tiene **conductor y checklist**; el nodo y el radio no;
- la persona no tiene custodia propia: tiene activos **entregados**.

### Lenguaje visual común

Lo que sí comparten: cabecera con resumen y acciones contextuales, pestañas de
secciones y línea de tiempo al final. Es un patrón reconocible sin que el
contenido sea intercambiable.

Se usan pestañas en lugar de apilar diez tablas: un expediente completo no cabe
legible en una columna, y obligar a recorrer toda la página para llegar al
historial es un mal flujo cotidiano.

## Datos faltantes

`field()` distingue **«No capturado»** de un valor vacío. Saber qué falta por
recoger es información útil para RRHH, y fingir un valor sería peor que admitir
el hueco.

## La vista resumen responde preguntas, no muestra contadores

```
¿Qué está pasando?      métricas de estado
¿Qué requiere atención? excepciones y alertas
¿Qué cambió?            altas, bajas, actividad reciente
¿Qué está pendiente?    solicitudes, órdenes, inventarios abiertos
¿Qué debo atender yo?   widget «Qué debo atender», filtrado por permisos
```

El último es el que evita que la pantalla sea ruido: sólo lista lo que **este**
usuario puede resolver. Ver `docs/30_DASHBOARD_CONFIGURABLE_Y_WIDGETS.md`.

## Responsive

| Ancho | Comportamiento |
|---|---|
| > 1100 px | barra lateral fija; rejilla de 12 columnas |
| 860–1100 px | widgets más anchos; barra lateral fija |
| < 860 px | barra lateral como panel deslizante con botón ☰ y velo |
| < 560 px | una columna; formularios apilados |

El gate E2E comprueba a 390 px que no haya desbordamiento horizontal y que el
panel se cierre solo al navegar.

## Cómo agregar una vista

1. Escribir `async function miVista(params) { … }` en `app/static/app.js`.
2. Registrarla en `VIEWS`.
3. Añadir una fila a `NAV` con su área, icono y **permiso**.
4. Si necesita endpoints nuevos, añadirlos a `REQUIRED_API` en
   `scripts/check-frontend-contract.py` para que el gate los proteja.

No hace falta tocar `index.html`.

## Convención de seguridad

La interfaz oculta lo que el usuario no puede hacer, pero eso es **ergonomía,
no seguridad**. La autorización real la impone el backend en cada endpoint, y
así lo verifican las pruebas de permisos.
