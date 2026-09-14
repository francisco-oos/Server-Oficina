# 10 · Roadmap incremental

## 0.1 · Oficina / Personal + Tracking Core

Identidad, relación laboral, asistencia, grupos, EPP, capacitación, casos, evidencia, importación, dashboard, permisos, eventos y auditoría.

### 0.1.0-alpha.2

Endurecimiento de empaquetado/despliegue en Latitude, iniciadores, validación por capa y documentación de investigación. **No abre Asset Core antes de cerrar Oficina.**

## 0.2 · Endurecimiento de Oficina/RRHH

- archivos reales;
- resolución UI de issues de importación;
- administración completa de proyectos/grupos;
- roster trabajo/descanso y grupos quincenales;
- responsable/supervisión temporal;
- vigencia/evidencia de capacitación;
- reportes;
- frontend E2E;
- exportaciones controladas.

## 0.3 · Control de Material / Asset Core

- activos genéricos e identificadores (serie/IMEI/QR/económico);
- custodia, ubicación, proyecto y estado como periodos temporales;
- check-in/out y movimientos;
- medidores/uso;
- observaciones de condición;
- mantenimiento base;
- cierre/conciliación de proyecto;
- transferencia sin cambiar identidad.

## 0.4 · Nodos / TX / Taller / vida útil

- nodos como especialización de asset;
- SERCEL/INOVA/Tendido Diario como fuentes;
- NodeHealth como fuente de salud/RUL;
- diagnóstico/falla/reparación/piezas/downtime;
- hermeticidad/pruebas/hibernación/listo campo;
- plantado/levantado/rotado/retorno;
- daño/robo/extravío/incautación/no reparable.

## 0.5 · Seguridad/HSE

- cursos y vigencias;
- Formatos HSE Campo/Supervisión Segura como adaptador;
- PDF original + JSON cifrado + hash + QR/folio + fotos/evidencia;
- línea/estaca/riesgo/evento;
- no alterar evidencia original.

## 0.6 · Transporte

- unidad, económico/serie/documentos;
- conductor y asignación temporal;
- radio/teléfono vinculados;
- checklist diario;
- km/combustible;
- PDF/fotos;
- historial por proyecto.

## 0.7 · Captura de campo offline y reconstrucción operacional

- captura de clics/reglas versionadas tipo Operación de Campo;
- store-and-forward local;
- acuse/reintento e idempotencia;
- no depender de Telegram como único transporte;
- consulta por persona/activo/proyecto/línea-estaca/fecha reuniendo fuentes sin ocultar contradicciones.

## Principio permanente

No avanzar cinco módulos al 40 %. Cerrar un bloque verificable, congelar contratos y agregar el siguiente.
