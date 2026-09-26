# 40 · Sincronización, conflictos y versionado

## Motor

Server Oficina no reimplementa P2P. Syncthing es candidato de transporte LAN;
la lógica de negocio sigue en Server Oficina.

## Capas

### Prevención: lease

Paco abre `Material.xlsx` y obtiene WRITE LEASE. Si Juan intenta escribir,
recibe aviso/sólo lectura. El lease expira si la PC desaparece.

### Detección: versiones

No se resuelve por `mtime`. Los cambios concurrentes se preservan y se
clasifican como BEFORE / AFTER / EQUAL / CONCURRENT.

### Reconciliación: tres vías

```text
          BASE
         /    \
      LEFT   RIGHT
```

Merge automático sólo si hay familia aprobada, clave estable y los dos lados no
cambiaron el mismo campo a valores distintos. Nunca se hace merge binario ciego
de XLSX.

## Offline

No se puede avisar en tiempo real si ambos equipos están desconectados. Al
regresar se conservan versiones, se localiza el ancestro común y se intenta
merge semántico. Cualquier ambigüedad requiere revisión.

## Borrado

Políticas: `ARCHIVE`, `REVIEW`, `DENY`. La réplica NAS no usa mirror/purge
como borrado ordinario. El purge futuro será explícito y verificado.

## Synology

Latitude = autoridad operativa local. Synology = réplica persistente. En Debian
se prefiere SMB/CIFS montado explícitamente; credenciales fuera de PostgreSQL.
Si NAS cae, los trabajos quedan pendientes.

## Lecciones de Organizador-Geografico-Evidencias

Se adoptan invariantes: temporal `.partial`, confinamiento de rutas, SHA-256,
reentrada, errores aislados, fallos sistémicos bloqueantes, no MIR/PURGE/MOVE,
concurrencia gobernada por el medio más lento y verificación posterior.

## Escala

La suite simula 24 clientes para dejar margen por encima del uso inicial. La
prueba física de red, SSD y Wi-Fi/LAN se hace en la Latitude.
