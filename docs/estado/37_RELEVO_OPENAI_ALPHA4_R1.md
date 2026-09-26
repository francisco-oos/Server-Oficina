# 37 · Relevo OpenAI R1 sobre alpha.4

Base exacta:

`0945a438a69ce33b34d532c2b7be7157b88f943b`

## Qué cambia

1. valida radio/teléfono por capacidad;
2. corrige homónimos en `es_conductor`;
3. alinea permiso de búsqueda y apertura de ficha por dominio;
4. agrega pruebas de regresión;
5. completa edición administrativa de perfiles personalizados y usuarios;
6. documenta como PARCIAL la autoridad HSE/casos.

## Qué NO se hace a la fuerza

No se concede `cases.resolve` global a HSE. Primero debe existir autoridad de
caso por área para no permitir que HSE resuelva casos ajenos.

## Gates al aplicar

```bash
python3 scripts/syntax-check.py app tests run.py
pytest -q
node --check app/static/app.js
node --check app/static/admin-management.js
python3 scripts/check-frontend-contract.py
./VALIDAR_BACKEND.sh
./VALIDAR_FRONTEND.sh
./VALIDAR_DESPLIEGUE.sh
./VALIDAR_FRONTEND_E2E.sh
```

## Manual

- Modo DEV sigue funcionando.
- Perfil personalizado: editar permisos y guardar.
- Usuario: asignar varios perfiles y cambiarlos.
- Nodo con `nodes.view` sin `assets.view`: buscar y abrir.
- Nodo usado como radio: 422.
- Tipo futuro con capacidad `radio`: aceptado.
- Dos personas homónimas: sólo el `person_id` asignado es conductor.
