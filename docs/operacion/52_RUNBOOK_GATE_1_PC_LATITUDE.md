# 52 · Runbook — Gate físico 1: una PC Windows ↔ Latitude

Fecha: 2026-09-27. Aplica a la candidata `0.2.0-alpha.1` de la rama de
sincronización. **Sólo archivos sintéticos en `LAB_SYNC`.** Ningún documento
real de RRHH, Seguridad, Transporte ni Control de Material.

Cada paso tiene un criterio de paro. Si se cumple, se detiene el gate, se
guarda evidencia y se reporta; no se improvisa sobre producción.

## 0 · Acceso

```bash
ssh adminoficina@server-oficina.local      # si mDNS resuelve
# si no: localizar la IP actual (DHCP) desde el router o en consola local:
hostname; hostname -I; ip -br a
```

La contraseña se escribe sólo en la terminal. Nunca en Git, documentos ni chat.

## 1 · PRE (sólo lectura)

```bash
cd ~/Server-Oficina                       # copia candidata
git fetch --all --prune && git checkout <rama> && git rev-parse HEAD
sudo ./scripts/evidencia-latitude.sh PRE
```

Revisar en el archivo `~/server-oficina-evidencia/PRE-*.txt`:

| Punto | Esperado | Paro si |
|---|---|---|
| `hostname` | `server-oficina` | otro nombre |
| `COLISION_RELEASE` | `NO` | `SI` |
| `/api/health` | JSON ok | falla antes de instalar (diagnosticar primero) |
| backup más reciente | `sha256sum -c` OK | SHA no verifica |
| `df -h /srv`, `/opt` | espacio para release + venv (~300 MB) | < 1 GB libre |
| VG | `serer-ficina-ADQ-vg` (typo histórico) | — **no renombrar** |

## 2 · Validación del paquete en copia limpia

```bash
TMP=$(mktemp -d)
git -C ~/Server-Oficina archive HEAD | tar -x -C "$TMP"
cd "$TMP" && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
PATH="$TMP/.venv/bin:$PATH" ./VALIDAR_SERVER_OFICINA.sh     # debe terminar en PACKAGE_OK
```

`VALIDAR_SERVER_OFICINA.sh` ahora exige que el árbol coincida exactamente con
`MANIFEST.sha256` (hash distinto, archivo faltante **o archivo no listado**).

## 3 · Instalación controlada

```bash
cd ~/Server-Oficina && ./INSTALAR_EN_TABLETA.sh
```

Marcadores esperados, en orden: `Release nueva: 0.2.0-alpha.1+<fecha>.g<commit>`,
`PRE_UPGRADE_BACKUP_OK`, JSON de health, `LOCAL_CLOUD_OK`.

| Salida | Significado |
|---|---|
| 5 | `/api/health` falló → `current` volvió a la release previa |
| 6 | colisión de release: no se tocó nada |
| 7 | el observador Nube Local no quedó estable → rollback completo |
| 8 | permisos de `files/` o `versions/` incompatibles con `serveroficina` |

El instalador ya no reutiliza ni sobrescribe directorios de release: la previa
queda intacta en `/opt/server-oficina/releases/` para rollback.

## 4 · POST

```bash
sudo ./scripts/evidencia-latitude.sh POST
readlink -f /opt/server-oficina/current
curl -fsS http://127.0.0.1:8080/api/health | python3 -m json.tool
systemctl status server-oficina server-oficina-backup.timer server-oficina-local-cloud --no-pager
journalctl -u server-oficina-local-cloud -n 20 --no-pager     # LOCAL_CLOUD_START ... versions_root=/srv/server-oficina/versions
```

## 5 · Syncthing del hub (LAB)

```bash
sudo ./scripts/preparar-nube-local-lab.sh            # precheck sin cambios
sudo ./scripts/preparar-nube-local-lab.sh --apply    # LAB_SYNC + syncthing@serveroficina-sync + UFW
```

La GUI del hub sólo escucha en `127.0.0.1:8384`. Desde la PC:
`ssh -L 8384:127.0.0.1:8384 adminoficina@server-oficina.local` y abrir
`http://127.0.0.1:8384`. Definir usuario/contraseña de GUI.

Configuración (hub y PC):

- Conexiones: descubrimiento local **sí**; global **no**; relays **no**; NAT **no**.
- Dispositivo: agregar el Device ID de la otra parte con dirección `dynamic`;
  sin introducer ni auto-accept.
- Carpeta: ID `lab-sync`, etiqueta `LAB_SYNC`; en el hub la ruta es
  `/srv/server-oficina/files/LAB_SYNC`; versionado **Staggered**; ignorar
  permisos **sí**; vigilar cambios **sí**.
- Registrar versiones de Syncthing de hub y PC (Debian puede traer 1.x y la PC
  2.x; CI prueba 2.1.5).

Registrar el share en Server Oficina **después** de que exista
`/srv/server-oficina/files/LAB_SYNC/.stfolder`:

```bash
JAR=$(mktemp); chmod 600 "$JAR"
read -rp "Usuario admin: " U; read -rsp "Contraseña: " P; echo
curl -fsS -c "$JAR" -H 'Content-Type: application/json' \
  -d "$(python3 -c 'import json,sys; print(json.dumps({"username":sys.argv[1],"password":sys.argv[2]}))' "$U" "$P")" \
  http://127.0.0.1:8080/api/auth/login >/dev/null; unset P
curl -fsS -b "$JAR" -H 'Content-Type: application/json' -d '{
  "code":"LAB_SYNC","name":"Laboratorio sincronización","owner_area_code":"LAB",
  "local_root":"/srv/server-oficina/files/LAB_SYNC","syncthing_folder_id":"lab-sync"}' \
  http://127.0.0.1:8080/api/local-cloud/shares
```

El archivo `$JAR` contiene la cookie de sesión: se usa en §6 y se borra al
terminar el gate (`rm -f "$JAR"`).

`local_root` fuera de `/srv/server-oficina/files` se rechaza con 422.

## 6 · Escenarios del gate 1

Archivos sintéticos: `Inventario_LAB.xlsx`, `Nota_LAB.docx`, `Nota_LAB.txt`,
`Binario_LAB.bin` (p. ej. 50 MB aleatorios). Registrar SHA-256 en PC
(`certutil -hashfile <archivo> SHA256`) y hub (`sha256sum`).

Consulta de historial:

```bash
curl -fsS -b "$JAR" http://127.0.0.1:8080/api/local-cloud/documents | python3 -m json.tool
curl -fsS -b "$JAR" http://127.0.0.1:8080/api/local-cloud/documents/<id>/versions | python3 -m json.tool
```

| # | Acción en la PC | Esperado en hub / Server Oficina |
|---|---|---|
| 1 | crear | mismo SHA; versión `MODIFIED`; objeto en `versions/sha256/..` |
| 2 | modificar | segunda versión; la primera sigue verificable |
| 3 | renombrar | `DELETED` en el nombre viejo + documento nuevo con el mismo SHA |
| 4 | mover a subcarpeta | igual que renombrar |
| 5 | borrar | tombstone `DELETED`; bytes siguen en ContentStore y `.stversions` |
| 6 | restaurar desde Papelera | versión `RECOVERED`; documento vivo |
| 7 | reiniciar PC | converge sin intervención |
| 8 | reiniciar Latitude | servicios arriba solos; converge |
| 9 | cortar red de la PC, editar, reconectar | converge; sin pérdida |
| 10 | apagar Internet (LAN arriba) | todo lo anterior sigue funcionando |

Atribución de dispositivo: sin Companion, el observador del hub **no** conoce
qué PC hizo cada cambio (`source_peer_id` vacío). Sólo las copias
`.sync-conflict-...-<DEVICE>` llevan el ID corto. No marcarlo como aprobado.

## 7 · Cambio de Wi-Fi / DHCP

Registrar IP anterior, IP nueva, tiempo hasta reconexión Syncthing y hasta
`/api/health` desde la PC. **No** editar Device IDs.

Riesgo conocido: `configurar-acceso-lan.sh` y el paso 5 permiten 8080/22000/21027
sólo desde la **subred** vigente al instalar. Si el router nuevo usa otra
subred, UFW bloqueará el acceso y habrá que re-ejecutar los scripts: con la
regla actual el gate de cambio de red **falla** en ese caso. Mismo prefijo con
otra IP DHCP sí debe pasar.

## 8 · Criterio para pasar al gate de 2 PCs

Todos los escenarios de §6 y §7 con evidencia (SHA, logs, tiempos), ningún
reinicio del observador (`NRestarts=0`), backup diario verificado y decisión
tomada sobre la regla UFW por subred.
