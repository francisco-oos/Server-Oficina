# 00 · LEEME PRIMERO — Server Oficina 0.1.0-alpha.2

Esta entrega **continúa** `0.1.0-alpha.1`; no crea otro proyecto ni sustituye el diseño acordado. Se conserva el monorepo/monolito modular FastAPI + UI web estática + PostgreSQL.

## Qué cambia en alpha.2

1. Se adapta el despliegue a la **Latitude 7220 real** preparada como `server-oficina`:
   - Debian 13;
   - Docker Engine/Compose;
   - PostgreSQL 18.6 en contenedor;
   - datos en `/srv/server-oficina`;
   - Docker/containerd en `/srv/docker`;
   - aplicación Python como servicio `systemd` sin privilegios.
2. Se elimina del flujo recomendado la instalación de PostgreSQL nativo en `/var`.
3. Se agregan iniciadores/operadores evidentes: `INICIAR`, `DETENER`, `REINICIAR`, `ESTADO`, `LOGS`, `VALIDAR`, `BACKUP`, `RESTORE`, `INSTALAR` y `ABRIR`.
4. Se separa la validación de **backend**, **frontend** y **despliegue**.
5. Se corrige documentación de pruebas: la base heredada tiene **11 pruebas**, no 7.
6. Se documentan las investigaciones nuevas de **vida útil/gestión de activos** y **RRHH operativo**, sin adelantar módulos incompletos ni cambiar el esquema funcional de 0.1.
7. Se conserva la regla: **persona ≠ relación laboral**, proyecto ≠ identidad, evento ocurrido ≠ registro tardío, evidencia ≠ resolución humana.

## Orden recomendado de trabajo

```text
1. LEER ESTE ARCHIVO
2. docs/01_PROBLEMA_Y_FINALIDAD.md
3. docs/02_ARQUITECTURA.md
4. docs/03_DECISIONES_Y_RAZONAMIENTO.md
5. docs/11_ESTADO_REAL_LATITUDE_20260911.md
6. docs/12_INVESTIGACION_CICLO_VIDA_ACTIVOS.md
7. docs/13_INVESTIGACION_RRHH_OPERATIVO.md
8. docs/14_MATRIZ_REQUISITOS_Y_ESTADO.md
9. docs/15_CONTRATOS_Y_GATES_MODULARES.md
10. docs/18_EVIDENCIA_OPERATIVA_Y_TRAZABILIDAD_DE_FUENTES.md
11. VALIDAR_SERVER_OFICINA.sh
12. INSTALAR_EN_TABLETA.sh
```

## Iniciadores

- `./INICIAR_SERVER_OFICINA.sh`
- `./DETENER_SERVER_OFICINA.sh`
- `./REINICIAR_SERVER_OFICINA.sh`
- `./ESTADO_SERVER_OFICINA.sh`
- `./LOGS_SERVER_OFICINA.sh`
- `./ABRIR_SERVER_OFICINA.sh`
- `./VALIDAR_SERVER_OFICINA.sh`
- `./VALIDAR_BACKEND.sh`
- `./VALIDAR_FRONTEND.sh`
- `./VALIDAR_DESPLIEGUE.sh`
- `./VALIDAR_FRONTEND_E2E.sh` (gate de navegador; requiere Playwright + Chromium/Chrome)
- `./BACKUP_SERVER_OFICINA.sh`
- `./RESTORE_SERVER_OFICINA.sh <directorio-backup>`
- `./INSTALAR_EN_TABLETA.sh`
- `./INSTALAR_ACCESO_ESCRITORIO.sh`

Los operadores ejecutan un bloque claro por acción y fallan ante el primer error útil. No ocultan fallos con cadenas largas de comandos.

## Estado de alcance

`0.1.0-alpha.2` sigue siendo el corte **Oficina / Personal + Tracking Core**. La investigación de Asset Core/Nodos/Taller se incorpora como diseño documentado para las siguientes versiones; **no se crean tablas paralelas ni un segundo Tracking Core** en esta entrega.
