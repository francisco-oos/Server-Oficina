# 01 · Problemática y finalidad

## Contexto real

El piloto nace dentro de **Adquisición de Datos**. La operación distribuye información entre Oficina/RRHH operativo, Control de Material, TX, Taller/Mantenimiento, Transporte, Seguridad/HSE y Supervisión. Hoy buena parte de esa información vive en Excel, CSV, formatos físicos, aplicaciones puntuales y conocimiento de cada responsable.

La dificultad no es únicamente "guardar datos". El problema aparece cuando hay que reconstruir un hecho y varias áreas tienen piezas distintas: quién estaba activo, con qué ID laboral en ese periodo, en qué grupo, qué cursos tenía, qué material se le entregó, qué reportó Taller, qué recibió TX, qué ocurrió en una línea/estaca, qué evidencia HSE existía y qué se recuperó físicamente.

Ejemplos que gobiernan el diseño:

- una persona de outsourcing puede renovar mensualmente, ser dada de baja y recontratada con **otro ID laboral**, sin dejar de ser la misma persona;
- un nodo puede pasar por diagnóstico, reparación, cambio de piezas, hermeticidad, TX, hibernación, almacén, entrega, plantado, levantado, rotado, retorno, daño, robo, extravío o incautación;
- un nodo no levantado puede explicarse por un reporte HSE en la misma línea/estaca (por ejemplo, un riesgo que impidió la recuperación);
- una incidencia de personal debe mostrar hechos/evidencias, no emitir una sanción automática;
- al cierre de cada proyecto debe poder conciliarse material inicial, compras/altas, movimientos, pérdidas, reparación, bajas y material sobreviviente/transferible.

## Problema raíz

Las fuentes actuales resuelven partes reales de la operación, pero carecen de una identidad, temporalidad, procedencia y auditoría comunes. Al comparar fuentes tardías o contradictorias, una celda final puede ocultar **cómo** se obtuvo el resultado.

## Finalidad

Construir una **memoria operacional verificable** que relacione personas, relaciones laborales, proyectos, activos, lugares, eventos, evidencias y decisiones humanas a través del tiempo.

El sistema **no es un veredicto**. Registra hechos, fuentes, historial y contexto. La decisión corresponde al área competente.

## Entrega inmediata

La versión `0.1.0-alpha.1` termina primero un corte vertical de **Oficina / Personal**:

- autenticación y permisos;
- persona independiente de su ID laboral;
- relaciones laborales/recontrataciones;
- proyecto y grupo temporal;
- directorio/búsqueda/expediente;
- importación con preview antes de commit;
- asistencia;
- EPP: solicitud abierta a perfiles autorizados, validación exclusiva RRHH;
- capacitación: RRHH programa/lista, HSE confirma;
- casos y evidencias con resolución humana;
- timeline auditable `occurred_at` / `recorded_at`;
- dashboard calculado desde base de datos.

## Futuro sin prometerlo como entregado hoy

El mismo Core queda preparado para incorporar después Control de Material, Node Tracking, TX, Taller/Mantenimiento, Transporte, Seguridad/HSE y Supervisión. No se implementan todavía sus workflows completos en esta alpha.
