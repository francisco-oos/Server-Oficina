# 21 · Evidencias, NAS y Organizador

## Objetivo

Los archivos pesados no deben convertir la Latitude de 128 GB en repositorio único. El patrón recomendado es:

```text
Windows / teléfono / app de campo
        │
        ├── carga mediante Server Oficina
        │              │
        │              ▼
        │        NAS/SMB configurado
        │
        └── copia directa al NAS / Organizador existente
                       │
                       ▼
              registrar/indexar en Server Oficina
```

Server Oficina es el **índice relacional y auditable**; el NAS puede seguir siendo el almacén principal.

## Nada hardcodeado

No se incorpora al código ninguna ruta de campamento, letra `F:` ni IP histórica. Un repositorio contiene:

- código;
- nombre;
- tipo `LOCAL` o `SMB`;
- `mount_point` Linux;
- URI/UNC canónica opcional;
- metadatos.

Las rutas históricas del Organizador sirven únicamente como procedencia documental y ejemplo de migración.

## Credenciales

Las credenciales SMB **no se guardan en PostgreSQL**. `CONFIGURAR_NAS_EVIDENCIAS.sh` crea un archivo root-only en `/etc/server-oficina` y un montaje CIFS reproducible.

## Fail-closed

Antes de escribir en un repositorio `SMB`, la aplicación comprueba que el punto realmente es un mount. Si el NAS desaparece:

- no crea una carpeta local sustituta;
- no finge que el upload fue remoto;
- responde error 503.

## Dos flujos compatibles

### A. Upload administrado

La UI recibe el archivo y lo escribe **en streaming por bloques** dentro del repositorio configurado; calcula SHA-256 durante la escritura, usa un archivo temporal en el mismo filesystem y sólo al finalizar lo promueve al nombre definitivo de forma atómica. Así fotos/videos grandes no se cargan completos en RAM y un corte de red no deja una evidencia parcial con nombre final. Registra:

- entidad/proyecto;
- nombre original;
- ruta relativa;
- SHA-256;
- tamaño;
- MIME;
- fecha de captura opcional;
- usuario y fecha de registro.

### B. Archivo ya existente

`/api/evidence/register-existing` permite indexar un archivo que ya fue copiado mediante Windows o por el Organizador. El servidor:

- no lo mueve;
- no lo renombra;
- verifica, tras resolver la ruta real, que permanezca dentro del repositorio y rechaza traversal/symlinks que escapen;
- calcula hash;
- evita duplicar el mismo hash/entidad.

## Bandeja opcional en la propia tableta

`CONFIGURAR_BANDEJA_EVIDENCIAS.sh` puede crear un recurso Samba de recepción. Es útil en campamento, pero no sustituye un NAS con mayor capacidad.

## Evolución prevista

- adaptador para JSON cifrado/PDF de Formatos HSE Campo;
- indexación de sidecars DJI (`MRK`, `SRT`, `JSON`, `XML`);
- clasificación asistida planificar→revisar→ejecutar, compatible con el principio del Organizador de Evidencias;
- deduplicación física opcional por hash sólo después de revisión humana.
