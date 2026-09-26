# 18 · Evidencia operativa y trazabilidad de fuentes

## Propósito

Separar claramente **acuerdo del proyecto**, **evidencia operativa del usuario**, **referencia normativa/técnica**, **patrón de repositorio externo** e **inferencia de diseño**. Una fuente inspira o demuestra una necesidad; no se convierte automáticamente en código ni en requisito legal.

## Evidencia interna revisada

| Evidencia | Fecha | Qué aporta a Server Oficina | Qué NO se hace |
|---|---:|---|---|
| `Nota_informativa_baja_45_equipos_celulares.docx` | 2026-08-13 | retiro técnico multifactor: batería, pantalla, desgaste, obsolescencia, fallas persistentes, reemplazos/incompatibilidad | no se copian números de serie ni se convierte una causa en regla universal |
| `Informe_Auditoria_Node_Health_Analyzer_2026.pdf` | 2026-07-16 | separa autonomía/SOH/riesgo; RUL experimental; exige calibración, confianza, verdad de campo y versionado | no se vende RUL como predicción validada ni se replica el algoritmo dentro del Core |
| `Examen Procedimiento general de control de inventarios de equipo sisimico.docx` | 2026-07 | entrega/recepción, conteo, serie/tipo, conciliación, incidencias de campo, bitácora | no se automatiza saltándose responsables/validaciones humanas |
| prototipo `Panel de Control · Cuadrilla de Adquisición` | 2026 | búsqueda integral de persona, jerarquía, asistencia, EPP, capacitación y directorio | no se conservan datos demo incrustados ni publicación pública de Google Sheets |

## Regla de procedencia

Toda incorporación material debe indicar una de estas clases:

```text
PROJECT_DECISION     acuerdo explícito del proyecto
INTERNAL_EVIDENCE    documento/flujo real de operación
STANDARD_REFERENCE   norma/estándar estudiado como referencia
REPO_PATTERN         patrón estudiado en repositorio propio/externo
IMPLEMENTED_RESULT   código + prueba verificable
DESIGN_INFERENCE     propuesta todavía no aprobada/implementada
```

La documentación debe evitar frases como “el sistema cumple ISO/NOM” salvo evaluación formal. La referencia se usa para diseñar datos y controles compatibles, no para declarar certificación o cumplimiento automático.

## Regla de privacidad

La documentación técnica de la release no debe incorporar listas completas de empleados, series, IMEI, teléfonos, fotografías, expedientes ni documentos internos. Sólo se guardan identificadores de la fuente y conclusiones necesarias de diseño. La evidencia original permanece en su repositorio/documento autorizado.
