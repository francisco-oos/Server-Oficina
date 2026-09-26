# 09 · Flujo de entrada de información de Oficina

## Carga masiva

```text
Excel/CSV
   ↓
Guardar original + SHA-256
   ↓
Parsear / normalizar encabezados
   ↓
Resolver persona por ID laboral o nombre único
   ↓
Generar PREVIEW
   ├── matched
   ├── new
   ├── issues
   └── attendance_cells
   ↓
Revisión humana
   ↓
COMMIT
   ↓
expediente + eventos + auditoría
```

## Captura individual

Altas/recontrataciones/cambios autorizados pasan por API/UI y generan evento/auditoría.

## Casos y evidencia

El reportante crea un hecho/caso y sube evidencia; la resolución es posterior y requiere permiso distinto.

## Formatos soportados en alpha

- `.csv` UTF-8/UTF-8 BOM;
- `.xlsx`;
- `.xlsm` sólo lectura de valores.

Encabezados reconocidos por aliases:

- clave/ID empleado;
- nombre;
- puesto/categoría;
- grupo/cuadrilla/brigada;
- estado/estatus;
- columnas fecha `dd/mm/yyyy`, `yyyy-mm-dd`, etc. para asistencia.

## Regla de seguridad

Una coincidencia de nombre múltiple genera issue `AMBIGUOUS_NAME` y la fila queda bloqueada. El sistema no decide qué persona es.

### Recontratación/cambio de ID detectado durante importación

Si un `employment_id` no existe pero el nombre coincide exactamente con una persona ya conocida, el importador genera `POSSIBLE_ID_CHANGE`, bloquea esa fila y exige revisión. Esto evita crear silenciosamente una nueva relación laboral o sobrescribir un ID anterior sin saber si se trata de recontratación, corrección o homónimo.
