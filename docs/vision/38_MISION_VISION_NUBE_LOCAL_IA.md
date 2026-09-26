# 38 · Misión y visión — Nube Local Inteligente de Server Oficina

## Misión

Convertir los archivos que una oficina ya produce en una **memoria operacional
verificable**, sin obligar a abandonar Excel, Word, PDF ni las herramientas que
ya funcionan.

Server Oficina debe permitir consultar personas, activos, documentos, hechos,
relaciones e incidencias conservando siempre el camino hasta la evidencia
original.

## Visión

Server Oficina es una nube privada local y una capa de inteligencia documental
desacoplada del hardware concreto:

- hoy la Dell Latitude 7220 + SSD es el primer hub;
- mañana el hub puede migrar a un servidor o NAS dedicado;
- las PCs conservan una experiencia estable aunque cambie la IP o el Wi-Fi;
- archivos pequeños/activos pueden estar replicados localmente;
- contenido pesado puede residir en almacenamiento de capacidad y aparecer
  mediante resolución/hidratación bajo demanda;
- PostgreSQL/Tracking Core son memoria verificable;
- la IA interpreta preguntas y documentos, pero no es fuente de verdad.

## Núcleo reutilizable y dominio

El núcleo debe evitar entrenamiento, nombres de formatos o reglas de una sola
empresa hardcodeados. Se separan:

```text
CORE REUTILIZABLE
  sincronización
  identidad
  documentos/versiones
  evidencia
  grafo
  búsqueda/consulta
  auditoría
  dashboard
       +
DOMAIN PACK / PERFIL DE OFICINA
  vocabulario
  formatos
  reglas
  autoridad de fuentes
  mapeos
  widgets
  capacidades
```

El proyecto actual incluye un dominio de Adquisición Sísmica; eso no convierte
ese dominio en el núcleo universal. El objetivo es que otras oficinas puedan
cargar su propio paquete de dominio sin reentrenar ni bifurcar el motor base.

## Acceso documental y autoridad

Las personas autorizadas de oficina pueden seguir el conjunto de documentos
sincronizados aunque pertenezcan a áreas distintas. La propiedad de un área
determina **autoridad sobre el dato**, no invisibilidad automática.

La sesión de una persona en una computadora aporta identidad de operador y
autoría. La sesión puede ser válida hasta 15 días, pero **presencia digital
actual** requiere heartbeat reciente; una sesión válida por sí sola no significa
que la persona esté en la oficina. Ambas señales complementan a RRHH y nunca
deben inventar asistencia, descanso o incapacidad.

## Norte de producto

> Archivo canónico; almacenamiento resoluble; base derivada; trazabilidad
> completa; IA como intérprete; humano y fuente competente como autoridad.

## Principios no negociables

1. No reemplazar el trabajo útil existente.
2. No duplicar captura.
3. Toda afirmación importante navega a evidencia.
4. Ocurrió ≠ se registró ≠ se sincronizó.
5. Hecho ≠ conclusión.
6. Propiedad del dato ≠ aislamiento documental.
7. Local-first y privado.
8. Degradación segura.
9. Sin borrado ni resolución de conflicto silenciosos.
10. Modelo/LLM reemplazable sin perder conocimiento.
11. Hardware reemplazable sin cambiar la identidad lógica del sistema.
12. El grafo es proyección reconstruible, no segunda verdad.
