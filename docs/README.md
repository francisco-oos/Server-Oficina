# Documentación de Server Oficina

La raíz de `docs/` se mantiene deliberadamente corta:

- `00_INDICE_DOCUMENTACION.md` — índice autoritativo.
- `INICIO_RAPIDO.md` — lectura inicial.
- `README.md` — esta guía.

El resto vive por responsabilidad:

```text
docs/
├─ vision/
├─ arquitectura/
├─ decisiones/
├─ investigacion/
├─ dominios/
├─ interfaz/
├─ seguridad/
├─ pruebas/
├─ operacion/
├─ desarrollo/
└─ estado/
```

Los reportes de ejecuciones concretas, auditorías y PRE/POST viven en
`../reports/`. Las decisiones estables pertenecen a `decisiones/`; las
comparaciones externas y fuentes a `investigacion/`; las instrucciones de
despliegue a `operacion/`.

No crear documentos nuevos en la raíz de `docs/` salvo que sean un punto de
entrada global.
