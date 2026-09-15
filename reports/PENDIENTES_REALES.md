# Pendientes reales

Lo que **no** está terminado. Esta release sigue siendo **alpha** aunque todos
los gates automáticos pasen.

## Revisión OpenAI R1 · pendientes adicionales

- **Autoridad HSE/casos:** la matriz declara HSE como autoridad de incidencias
  HSE, pero `CaseRecord` todavía no identifica el área propietaria y
  `cases.resolve` es global. Debe modelarse autoridad por caso antes de
  conceder resolución global a HSE.
- **Administración de perfiles/usuarios:** el backend ya permite editar perfiles
  personalizados y reasignar perfiles de usuarios; OpenAI R1 agrega la interfaz
  que faltaba para usar esas capacidades.

## Parcial: funciona con límite declarado

| # | Qué | Qué falta exactamente |
|---|---|---|
| 1 | **Rotación trabajo/descanso** | Se capturan y se muestran los días (21×7). No se genera calendario ni se proyecta quién está de descanso en una fecha futura. El widget «Personal en descanso» lee la asistencia del día, no la rotación. |
| 2 | **Fotografías en el checklist de transporte** | Se pueden adjuntar como evidencias del activo. No hay captura de foto integrada en el formulario de checklist ni miniaturas en la ficha. |
| 3 | **Observaciones sobre la persona** | Existen notas en casos y `metadata_json` en la ficha laboral. No hay bitácora de observaciones con su propia pantalla e historial. |
| 4 | **«Entregado» como cierre de taller** | Se representa con `MAINTENANCE_OUT` más el movimiento de custodia. No hay acuse de entrega firmado ni constancia imprimible. |
| 5 | **Reordenar widgets con arrastrar y soltar** | Se reordena con botones ▲▼, que funcionan bien con guantes. No hay drag & drop. |
| 6 | **Paginación de listados** | Hay límites duros (100–300 filas). Con inventarios de varios miles de activos hará falta paginar de verdad. |

## Pendiente: no implementado

| # | Qué | Por qué no entró |
|---|---|---|
| 7 | **Módulo de Ingesta Documental por Área** | Lo desarrollará otro programador. Esta entrega deja los **contratos** listos en `docs/34_CONTRATO_INGESTA_DOCUMENTAL.md` para que se integre con `ImportBatch`/`ImportIssue` y no nazca una versión incompatible. |
| 8 | **Herramienta de migraciones** | Mientras se respete «sólo se agregan tablas» no hace falta. Será necesaria en cuanto haya que alterar una columna con datos en producción. |
| 9 | **Exportaciones e informes imprimibles** | No estaban en el encargo. Se mencionan porque la oficina acabará pidiéndolos. |

## Gates físicos pendientes en la Latitude

Ninguno de estos puede cerrarse desde un entorno de construcción. Requieren el
equipo real.

| # | Gate | Cómo cerrarlo |
|---|---|---|
| 10 | Actualización `alpha.3 → alpha.4` sobre la instalación real | `./INSTALAR_EN_TABLETA.sh`, verificando el backup pre-upgrade y que `create_all` añade las 6 tablas nuevas sin tocar las existentes |
| 11 | Rollback controlado de release | forzar un fallo de `/api/health` y comprobar que el symlink `current` revierte |
| 12 | E2E de navegador **en la Latitude** | el recorrido pasa en este entorno; falta ejecutarlo en el hardware y resolución reales |
| 13 | Repositorio SMB/NAS real | montar el NAS de la oficina, cargar evidencia real y comprobar el comportamiento fail-closed desmontándolo |
| 14 | Importación de archivos reales de Oficina/Material | los formatos reales suelen tener sorpresas que ningún CSV de ejemplo reproduce |
| 15 | Pruebas multiusuario con perfiles reales | varias personas a la vez, cada una desde su área |
| 16 | Backup integral + restore integral **después** de operar alpha.4 | restaurar a base temporal y arrancar contra ella |
| 17 | Revisión visual del usuario | la interfaz se rehízo por completo; hace falta que quien la usa a diario la vea antes de darla por buena |
| 18 | Estabilidad prolongada | días de operación continua, reinicios y concurrencia física |

## Criterio para dejar de llamarla alpha

Cerrar los puntos **10 a 18**. Los puntos 1 a 6 son limitaciones conocidas que no
impiden operar; los 7 a 9 son trabajo futuro planificado.

## Lo que esta entrega NO afirma

- No afirma que la interfaz sea la definitiva: se rehízo entera y necesita el
  juicio de quien la usa en campo.
- No afirma que los formatos reales de la oficina importen sin ajustes.
- No afirma haber probado el NAS real, ni concurrencia física, ni un ciclo
  completo de respaldo y restauración sobre datos de producción.
- No declara éxito por compilar ni por tener los gates en verde.
