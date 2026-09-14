# 15 · Contratos y gates modulares

## Contrato de fuente

Toda fuente externa futura debe declarar:

- `source_type` y versión;
- archivo/mensaje original cuando sea posible;
- hash;
- `occurred_at` y `recorded_at`;
- proyecto/contexto;
- entidad identificada o issue de resolución;
- reglas de transformación versionadas;
- usuario/proceso que confirmó el commit.

## Contrato de módulo

Un módulo puede leer identidades del Core, pero no debe crear su propia copia paralela de persona/activo/proyecto. Debe registrar su dato especializado y emitir evento transversal cuando el hecho sea relevante.

## Gates por bloque

### Oficina/RRHH
- datos reales en copia;
- rehire/outsourcing;
- import issues;
- permisos;
- curso vigente/vencido cuando se implemente;
- backup/restore.

### Asset Core
- alta única por identificadores;
- custodia temporal;
- ubicación temporal;
- proyecto temporal;
- movimiento reversible/auditable;
- cierre de proyecto;
- no duplicar activo al transferir.

### Nodos/TX/Taller
- importar fuentes SERCEL/INOVA/NodeHealth;
- diagnóstico/falla/mantenimiento;
- componente/reparación;
- prueba y listo-campo;
- plantado/levantado/rotado/retorno;
- pérdida/robo/incautación con evidencia.

### HSE
- original PDF;
- JSON cifrado embebido;
- hash;
- vínculo línea/estaca/proyecto/persona cuando exista;
- lectura sin alterar evidencia original.

### Transporte
- unidad e identificadores;
- conductor/asignación temporal;
- checklist con evidencia;
- km/combustible;
- documentos y vigencias;
- historial por proyecto.

## No negociables

- no datos reales hardcodeados;
- no silencioso “último valor gana” ante contradicciones;
- no borrado de historia para mostrar estado actual;
- no decisión disciplinaria automática;
- no copiar repositorios externos sin revisión de licencia/procedencia;
- no nuevo servicio/microservicio sin una razón operacional demostrada.
