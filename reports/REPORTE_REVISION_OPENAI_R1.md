# Reporte de revisión independiente OpenAI R1

Fecha: 2026-09-14

Base auditada:

- rama `claude/server-oficina-review-evolution-ybrrp7`
- commit `0945a438a69ce33b34d532c2b7be7157b88f943b`
- versión `0.1.0-alpha.4`

## Dictamen

Alpha.4 es una mejora sustancial y debe conservarse como base. Los parches R01
y R02 previos de OpenAI quedan supersedidos: aplicarlos crearía dos diseños
paralelos de Dashboard/Localizador.

La segunda revisión detectó huecos no cubiertos por las 62 pruebas declaradas.

## OAI-01 · Transporte valida existencia, no semántica, de radio/teléfono

`radio_asset_id` y `phone_asset_id` aceptan cualquier `Asset` existente. La UI
filtra por capacidad, pero un cliente directo podría guardar un nodo como radio.

Corrección: validar capacidades `radio` y `phone` en la API, sin hardcodear
nombres de tipo.

## OAI-02 · Homónimos pueden falsear `es_conductor`

`lookup.person_summary()` comparaba `driver_name == person.full_name`.

Corrección: comparar `transport.driver_person_id == person.id`.

## OAI-03 · Búsqueda y apertura de nodos no usan la misma autorización

La búsqueda deja ver un nodo con `nodes.view`; la ruta de ficha exigía primero
`assets.view`. Un perfil `dashboard.view + nodes.view` encontraba el nodo pero
recibía 403 al abrirlo.

Corrección: la ruta se autentica y luego exige sólo el permiso de su dominio.

## OAI-04 · Autoridad HSE sobre casos es todavía declarativa

La matriz marca HSE como autoridad de `HSE_INCIDENT`, pero el rol base HSE no
tiene `cases.resolve` y `CaseRecord` no identifica el área propietaria. Darle el
permiso global sin más permitiría resolver casos ajenos.

Estado correcto: PARCIAL hasta introducir autoridad/área del caso mediante una
evolución aditiva y pruebas de aislamiento por área.

## OAI-05 · UI administrativa no exponía capacidades ya existentes

El backend ya permite editar perfiles personalizados y cambiar perfiles de
usuarios. La UI alpha.4 sólo permitía creación y cambio de área.

Se añade una extensión modular que:
- edita descripción/permisos de perfiles personalizados;
- mantiene bloqueados los perfiles base;
- crea usuarios con múltiples perfiles;
- cambia perfiles de usuarios existentes;
- conserva la protección del backend para el último ADMIN.

## Verificación hecha por OpenAI

Revisión de código y pruebas sobre:
RBAC, áreas, dashboard, widgets, transporte, búsqueda/expedientes, runtime,
seguridad, pendientes y tests alpha.4.

En este runner no existe conectividad de red hacia GitHub, por lo que no se
pudo clonar la rama para repetir los 62 tests completos. Por transparencia:
OpenAI no reclama haberlos reejecutado.

Sí se ejecutaron sobre este relevo:
- `node --check app/static/admin-management.js`;
- `py_compile tests/test_openai_alpha4_review.py`;
- un harness dirigido de reglas de regresión;
- validación semántica del contenido del patch.

Al aplicar el patch en el repositorio real, el siguiente gate obligatorio es
`VALIDAR_SERVER_OFICINA.sh` y después el E2E.

## Publicación GitHub

La conexión actual informa `push=true` y ChatGPT está configurado para permitir
todas las acciones del plugin, pero GitHub devuelve HTTP 403 a create_branch,
update_ref y create_blob: `Resource not accessible by integration`.

Por eso no se tocó `main` ni la rama de Claude y se entrega patch reproducible.
