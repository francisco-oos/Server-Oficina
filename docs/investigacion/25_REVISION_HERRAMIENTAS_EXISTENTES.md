# 25 · Revisión de herramientas existentes

## Propósito

Investigar software existente para aprender patrones y evitar reinventar problemas resueltos, sin sustituir Server Oficina por otro producto ni copiar código incompatible.

## Snipe-IT

Referencia: `grokability/snipe-it` (AGPL-3.0).

Patrones útiles estudiados:

- asset tag e identidad individual;
- check-in/check-out;
- custodia/responsabilidad;
- campos personalizados;
- importación y auditoría.

Decisión: **no integrar la aplicación ni copiar código**. Server Oficina tiene requisitos de nodos sísmicos, operaciones por línea/estaca, temporalidad y RRHH que no justifican adoptar Snipe-IT como núcleo.

## Ralph / GLPI

Patrones de estudio:

- ciclo de vida de activos;
- ubicación;
- CMDB/inventario;
- incidencias/mantenimiento;
- historial de cambios.

Decisión: estudio arquitectónico únicamente. La Latitude y el dominio de Adquisición favorecen el monolito FastAPI existente.

## OpenBoxes

Patrones de estudio:

- movimiento de inventario;
- recepción/transferencia;
- conciliación y existencias.

Decisión: rescatar conceptos de movimientos y cortes, no convertir nodos en SKU fungibles. Un nodo/IMEI/serie conserva identidad individual.

## Casbin

Se estudió como motor de políticas. Alpha.3 mantiene RBAC propio por ser pequeño, explícito y ya funcional. Casbin queda diferido si aparecen políticas ABAC/condicionales difíciles de expresar con la matriz actual.

## Herramientas propias

### Tendido-Diario-revision

Se preservan ideas de conciliación SERCEL/INOVA, prioridad de fuentes y comparación contra histórico.

### NodeHealthAnalyzer

Se prepara adaptador conceptual para observaciones de salud, anomalías y RUL; no se promociona una predicción a hecho sin validación.

### Formatos-HSE-Campo / SupervisiónSeguraManage

Se preserva el patrón de evidencia original + JSON cifrado + hash + datos normalizados. La integración HSE se mantiene como adaptador futuro, no reescritura.

## Conclusión

La estrategia sigue siendo **núcleo propio ligero + adaptadores + patrones aprendidos**, no Frankenstein de frameworks.
