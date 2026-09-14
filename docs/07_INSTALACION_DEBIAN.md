# 07 · Instalación Debian / Latitude

## Supuestos

- Debian ya instalado y con red funcional;
- usuario con `sudo`;
- el ZIP se copia completo a la tablet;
- Internet disponible durante la **primera instalación de dependencias Python** o un mirror/wheelhouse preparado. El paquete no incluye `venv` ni dependencias binarias.

## Instalación

Desde la raíz descomprimida:

```bash
sudo bash scripts/install-debian.sh
```

El instalador:

1. instala Python, PostgreSQL, `rsync`, `curl`, `openssl`;
2. crea usuario de servicio `serveroficina`;
3. copia a `/opt/server-oficina`;
4. crea `/var/lib/server-oficina/{imports,evidence,backups}`;
5. crea usuario/base PostgreSQL;
6. genera configuración en `/etc/server-oficina/server-oficina.env`;
7. instala `systemd`;
8. ejecuta health check;
9. habilita backup diario.

Luego abre:

```text
http://IP_DE_LA_TABLET:8080
```

La primera apertura permite crear **un único administrador inicial**; después el endpoint queda bloqueado.

## Verificación

```bash
sudo systemctl status server-oficina
curl http://127.0.0.1:8080/api/health
sudo journalctl -u server-oficina -f
```

## Backup

```bash
sudo /opt/server-oficina/scripts/backup.sh
```

Incluye `pg_dump`, evidencia/importaciones y `SHA256SUMS`.

## Restore

```bash
sudo /opt/server-oficina/scripts/restore.sh /var/lib/server-oficina/backups/AAAAMMDD-HHMMSS
```

## Gate de producción

Esta alpha **no se declara estable** hasta probar en Latitude física:

- reinicio del SO;
- acceso desde al menos PC + teléfono LAN;
- importación con copias de archivos reales;
- usuarios/permisos reales;
- backup + restore completo;
- comportamiento con pérdida/reinicio de red.
