# 07 · Instalación Debian / Latitude — alpha.2

## Importante

Esta guía sustituye el instalador alpha.1. **No instale PostgreSQL nativo** ni use `/var/lib/server-oficina` en la Latitude preparada.

## Precondiciones verificadas

- Debian 13 Trixie amd64;
- SSH;
- UFW;
- Docker Engine + Compose;
- `/srv/server-oficina`;
- `/srv/docker`;
- PostgreSQL 18.6 probado con persistencia y restore.

## Instalar release

```bash
chmod +x *.sh scripts/*.sh
./VALIDAR_SERVER_OFICINA.sh
./INSTALAR_EN_TABLETA.sh
```

El instalador:

1. conserva/genera el secreto PostgreSQL en `/srv/server-oficina/secrets/postgres_password`;
2. instala el compose canónico en `/srv/server-oficina/app/infra/compose.yml`;
3. levanta PostgreSQL 18.6 con datos en `/srv/server-oficina/data/postgres`;
4. publica PostgreSQL sólo en `127.0.0.1:5432`;
5. instala la release en `/opt/server-oficina/releases/<VERSION>`;
6. crea `.venv` por release;
7. actualiza `/opt/server-oficina/current`;
8. genera `/etc/server-oficina/server-oficina.env`;
9. instala/arranca `server-oficina.service`;
10. instala backup timer;
11. prueba `/api/health`;
12. si UFW está activo, intenta permitir 8080 únicamente desde la subred LAN actual.

## Estado

```bash
./ESTADO_SERVER_OFICINA.sh
```

## Abrir localmente

```bash
./ABRIR_SERVER_OFICINA.sh
```

Desde otro equipo autorizado use `http://IP_DE_LA_TABLET:8080`.

## Cambio de red

Si la tableta cambia de red/subred:

```bash
sudo ./scripts/configurar-acceso-lan.sh
```

Revise reglas UFW anteriores antes de dejarlas acumuladas.

## Backup / Restore

```bash
./BACKUP_SERVER_OFICINA.sh
./RESTORE_SERVER_OFICINA.sh /srv/server-oficina/backups/server-oficina/AAAAMMDD-HHMMSS
```

No ejecute restore sobre datos reales sin confirmar el backup objetivo y una ventana de mantenimiento.
