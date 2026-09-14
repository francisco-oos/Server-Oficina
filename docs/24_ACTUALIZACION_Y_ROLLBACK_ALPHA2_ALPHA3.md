# 24 · Actualización y rollback alpha.2 → alpha.3

## Principio

La Latitude instalada no se reinstala. Se promueve una release versionada.

```text
/opt/server-oficina/releases/0.1.0-alpha.2
/opt/server-oficina/releases/0.1.0-alpha.3
/opt/server-oficina/current -> release activa
```

## Compatibilidad de datos

Alpha.3 **no modifica columnas heredadas** de alpha.2. Añade tablas nuevas mediante `Base.metadata.create_all()`. Esto evita una migración destructiva en esta fase.

Las tablas alpha.2 de personas, contrataciones, EPP, cursos, casos y auditoría permanecen intactas.

## Instalador

`scripts/install-tablet.sh` ejecuta:

1. copia release;
2. crea `.venv`;
3. instala dependencias;
4. ejecuta `verify-package.sh`;
5. genera `pg_dump -Fc` pre-upgrade;
6. verifica PostgreSQL healthy;
7. conserva el `current` anterior;
8. promueve alpha.3;
9. reinicia servicio;
10. verifica `/api/health`;
11. si falla, restaura el symlink anterior y reinicia alpha.2.

## Alcance del rollback

Como alpha.3 sólo añade tablas, alpha.2 puede ignorarlas. El rollback de release no elimina automáticamente las tablas nuevas. El dump pre-upgrade existe para una restauración completa si alguna investigación posterior demuestra necesidad.

## Regla futura

Cuando una release requiera `ALTER`, borrados o transformaciones de datos, `create_all()` dejará de ser suficiente y se incorporará una herramienta de migraciones versionadas (por ejemplo Alembic) antes de promoverla.
