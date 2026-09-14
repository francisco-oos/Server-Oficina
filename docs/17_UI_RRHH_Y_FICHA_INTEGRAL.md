# 17 · Dirección UI RRHH y ficha integral

## Referencia rescatada

El prototipo previo “Panel de Control · Cuadrilla de Adquisición” dejó una intención UX valiosa:

- KPIs de personal;
- búsqueda inmediata por clave o nombre;
- ficha de trabajador en una sola vista;
- puesto, grupo, estado;
- EPP;
- capacitaciones;
- asistencia por días;
- jerarquía/personal a cargo;
- directorio filtrable.

**No se rescatan los datos demo incrustados ni el enfoque de publicar Google Sheets en la web.** Server Oficina usa PostgreSQL, RBAC, importación controlada y LAN.

## Ficha integral objetivo

La ficha debe crecer por composición de módulos:

```text
IDENTIDAD
  nombre + person_id

RELACIÓN LABORAL VIGENTE
  ID laboral + proveedor + puesto + proyecto + fechas

OPERACIÓN
  grupo + responsable + turno/descanso + campamento

RRHH/HSE
  asistencia + EPP + cursos vigentes + casos/evidencia permitidos

CUSTODIA
  radio + teléfono + unidad + otros activos

HISTORIA
  timeline temporal + fuentes + auditoría
```

No se debe construir una “tabla maestra” duplicando todo. La UI consulta vistas/API que resuelven relaciones temporales.

## Criterios de interfaz

- pocos clics para captura de campo/oficina;
- buscar antes que navegar árboles profundos;
- estados legibles y filtros rápidos;
- conflicto/ambigüedad visible, no resuelto silenciosamente;
- interfaz responsive para PC/tablet/teléfono;
- modo LAN sin CDN obligatoria;
- no mostrar información sensible a roles que no la necesitan;
- mostrar procedencia/fecha cuando un dato pueda estar atrasado.
