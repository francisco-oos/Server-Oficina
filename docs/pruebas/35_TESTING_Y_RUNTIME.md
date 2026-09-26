# 35 · Pruebas y aislamiento del runtime

## El problema reportado

Ejecutar `VALIDAR_SERVER_OFICINA.sh` **a mano** contra la release ya instalada
en `/opt/server-oficina/current` fallaba antes de recolectar una sola prueba:

```
PermissionError: [Errno 13] Permission denied:
  '/opt/server-oficina/current/tests/runtime'
```

Durante la instalación las pruebas sí pasaban, porque el instalador corre como
root sobre un árbol todavía escribible. La validación posterior, hecha por el
usuario de servicio sobre el árbol ya desplegado, no.

## Causa raíz

`tests/conftest.py` fijaba sus rutas de escritura **dentro del árbol de
código**:

```python
TEST_DB = Path(__file__).parent / "test.db"
os.environ["SERVER_OFICINA_DATA_DIR"] = str(Path(__file__).parent / "runtime")
```

Y `app/core/config.py` crea el `data_dir` en tiempo de importación, así que el
fallo ocurría al importar el `conftest`.

Eran cuatro escrituras al árbol, no una:

| Artefacto | Quién lo escribía |
|---|---|
| `tests/runtime/` | `SERVER_OFICINA_DATA_DIR` del conftest |
| `tests/test.db` | base SQLite del conftest |
| `.pytest_cache/` | caché de pytest en el rootdir |
| `__pycache__/` | `python -m compileall` del gate de backend |

## Cómo NO se arregló

- ❌ `chmod -R 777` — deja el código desplegado modificable por cualquier usuario.
- ❌ hacer escribible `/opt` — contradice el endurecimiento del servicio systemd
  (`ProtectSystem`, `NoNewPrivileges`).
- ❌ ejecutar la validación como root — enmascara el problema en lugar de
  resolverlo, y no es lo que hace el operador.

## Cómo se arregló

**Las pruebas no escriben nunca dentro del árbol de código.**

### 1 · Runtime temporal (`tests/_runtime.py`)

```
SERVER_OFICINA_TEST_RUNTIME   si el operador la define (se respeta y no se borra)
                              ↓ si no
tempfile.mkdtemp()            directorio privado, borrado al terminar el proceso
```

Es idempotente por proceso: base de datos, `data_dir` y artefactos comparten una
sola raíz y se limpian juntos.

### 2 · `tests/conftest.py`

Apunta la base y el `data_dir` a ese runtime. Los `os.environ` se fijan antes de
importar la aplicación, porque `app.db.base` resuelve la configuración en tiempo
de importación.

### 3 · `pytest.ini`

```ini
addopts = -q -p no:cacheprovider
```

Desactiva la caché de pytest, que se escribiría en el rootdir. Para usar `--lf`
en desarrollo: `pytest -p cacheprovider -o cache_dir=/ruta/escribible`.

### 4 · `scripts/syntax-check.py` sustituye a `compileall`

`compileall` tiene como propósito *escribir* `__pycache__`. Para el gate sólo
interesa detectar `SyntaxError`, y `compile()` en memoria da exactamente esa
garantía sin tocar el disco. El gate exporta además `PYTHONDONTWRITEBYTECODE=1`.

## Verificación

Reproducido y comprobado con un árbol real en modo sólo lectura y un usuario no
privilegiado:

```bash
chmod -R a-w /ruta/release
su usuario_sin_privilegios -c 'cd /ruta/release && pytest -q'
# 59 passed
# artefactos escritos dentro del árbol: 0
```

`tests/test_runtime_paths.py` (5 pruebas) fija la corrección: comprueba que el
runtime, la base y el `data_dir` quedan **fuera** del árbol y que los artefactos
culpables no reaparecen.

## Gates

| Script | Qué verifica |
|---|---|
| `VALIDAR_BACKEND.sh` | sintaxis sin escribir + 59 pruebas |
| `VALIDAR_FRONTEND.sh` | sintaxis JS + contrato de interfaz |
| `VALIDAR_DESPLIEGUE.sh` | sintaxis shell + contratos de despliegue |
| `VALIDAR_FRONTEND_E2E.sh` | recorrido real de navegador |
| `VALIDAR_SERVER_OFICINA.sh` | todos los anteriores + `sha256sum -c MANIFEST.sha256` |

Ninguno escribe en el árbol de código.

> **Nota sobre el manifiesto.** `VALIDAR_SERVER_OFICINA.sh` verifica
> `MANIFEST.sha256`. Si modifica archivos en desarrollo, ejecute
> `./GENERAR_MANIFEST.sh` antes de volver a pasar el gate completo. Sobre una
> release instalada no debe hacer falta: si falla, el contenido desplegado no
> coincide con el publicado y eso es justo lo que el gate debe detectar.

## Composición de la suite

| Archivo | Pruebas | Cubre |
|---|---:|---|
| `test_core.py` | 3 | bootstrap, login, RBAC |
| `test_temporal.py` | 1 | `occurred_at` ≠ `recorded_at` |
| `test_admin_and_lifecycle.py` | 3 | usuarios, ciclo laboral |
| `test_training_cases_imports.py` | 4 | cursos, casos, importaciones |
| `test_alpha3_operational.py` | 15 | Asset Core, nodos, taller, inventario, evidencias |
| `test_alpha3_acceptance_story.py` | 1 | historia transversal de aceptación |
| `test_alpha4_areas_and_dashboard.py` | 12 | áreas, autoridad, vista resumen configurable, modo DEV |
| `test_alpha4_transport.py` | 7 | dominio de Transporte |
| `test_alpha4_dossiers_and_search.py` | 8 | expedientes por dominio y búsqueda transversal |
| `test_runtime_paths.py` | 5 | aislamiento del runtime |
| **Total** | **59** | |

## Nota sobre estado compartido

Las pruebas comparten un `TestClient` de sesión y una sola base. Es deliberado:
ejercita el arranque real una vez y permite historias de aceptación que cruzan
varias pruebas. A cambio, cada prueba debe usar **códigos e identificadores
propios** (`P-DOS`, `UN-100`, `EMP-TR-100`) y aceptar `409` cuando crea algo que
otra prueba pudo haber creado ya.
