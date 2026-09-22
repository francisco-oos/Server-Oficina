# 38 · Misión y visión — Nube Local Inteligente de Server Oficina

## Misión

Convertir los archivos que la oficina ya produce en una **memoria operacional
verificable**, sin obligar a las áreas a abandonar Excel, Word, PDF ni sus
formatos de entrega.

Server Oficina debe permitir responder rápidamente preguntas sobre personas,
activos, ubicaciones, cursos, custodias, incidencias y operaciones, conservando
siempre la ruta hacia la evidencia original que respalda cada dato.

## Visión

La Dell Latitude 7220 + SSD funciona como una **nube privada local de la
oficina**:

- las computadoras siguen trabajando con carpetas y archivos normales;
- la LAN continúa operando aunque no exista Internet;
- la Latitude mantiene la copia de trabajo, versiones, contexto estructurado y trazabilidad;
- Synology es una réplica organizada y persistente, no una dependencia para poder trabajar;
- PostgreSQL/Tracking Core son la memoria verificable;
- la IA local interpreta ambigüedades, pero nunca es la fuente de verdad.

## Norte de producto

> **Archivo canónico; base de datos derivada; trazabilidad completa; IA como
> intérprete; humano y área competente como autoridad.**

La pantalla principal no existe para contar cuántas modificaciones hizo un
departamento. Existe para contestar preguntas operativas: cuántos cabos están
activos, dónde está una persona, quién tiene un radio, dónde se vio por última
vez un nodo, qué curso tiene vigente un conductor o de qué documento salió una
afirmación.

## Principios no negociables

1. No reemplazar el trabajo útil existente.
2. No duplicar captura.
3. Toda afirmación debe navegar a evidencia.
4. Ocurrió ≠ se registró ≠ se sincronizó.
5. Hecho ≠ conclusión.
6. Cada dato tiene área propietaria.
7. Local-first y privado.
8. Degradación segura.
9. Sin borrado silencioso.
10. El grafo es proyección reconstruible, no segunda verdad.

## Ejemplo de valor

Una búsqueda de una persona combina su situación laboral, grupo/campamento,
cursos, licencia, unidad, radio, teléfono y activos actuales. Una búsqueda de un
radio muestra custodia, daños, taller y documentos que originaron los eventos.
Una búsqueda de nodo reconstruye taller → entrega → campo → sismógrafos →
checador → retorno/excepción.

Éste es el criterio para aceptar o descartar futuras funciones: si no mejora
consulta, trazabilidad, coordinación o reducción de captura/revisión manual, no
pertenece al núcleo de Server Oficina.
