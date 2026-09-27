#!/usr/bin/env python3
from __future__ import annotations

"""Laboratorio de ``scripts/restore.sh`` contra un PostgreSQL real.

Se crea un clúster PostgreSQL efímero (binarios de la distribución) y
``docker exec -i server-oficina-postgres <herramienta>`` se redirige a él. El
script de restauración real se ejecuta sin modificar dentro de un namespace de
montaje donde ``/srv/server-oficina`` y ``/etc/server-oficina`` son temporales;
``systemctl`` y ``curl`` (health) son stubs. El health consulta la base real,
así puede fallar sólo cuando la base restaurada está activa.

Escenarios: dump truncado (defecto reproducido con el script anterior y
detectado por el nuevo antes de tocar nada), fallo de ``pg_restore`` a mitad de
la restauración (rol ausente), SHA inválido, tar dañado o con rutas fuera de
``imports/``/``evidence/``, health que falla tras el intercambio (vuelta atrás
completa) y restauración correcta de un esquema más antiguo con archivos extra
en ``data/app`` (conservados, nunca borrados).

NO sustituye al gate físico (PostgreSQL 18.6 en Docker en la Latitude).

    sudo -E LAB_ROOT=/tmp/restore-lab python3 tests/integration/restore_lab.py
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LAB = Path(os.environ.get("LAB_ROOT", REPO / "runtime" / "restore-lab")).resolve()
BIN = LAB / "bin"
STATE = LAB / "state"
NS = {"/srv/server-oficina": LAB / "srv", "/etc/server-oficina": LAB / "etc-so",
      "/opt/server-oficina": LAB / "opt"}
PORT = "55432"
EVIDENCE: dict = {"scenarios": []}


def pg_bindir() -> Path:
    found = sorted(Path("/usr/lib/postgresql").glob("*/bin/pg_restore"))
    if found:
        return found[-1].parent
    pg_restore = shutil.which("pg_restore")
    if not pg_restore:
        raise SystemExit("PostgreSQL (servidor y cliente) no está instalado")
    return Path(pg_restore).parent


PGBIN = pg_bindir()
PGROOT = Path(tempfile.mkdtemp(prefix="so-restore-lab-pg-"))  # fuera de HOME: accesible al usuario postgres
PGDATA, PGSOCK = PGROOT / "data", PGROOT / "sock"


def sh(*args, check=True, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=check, text=True, capture_output=True, **kwargs)


def psql(sql: str, db: str = "server_oficina", check: bool = True) -> str:
    return sh(str(PGBIN / "psql"), "-h", str(PGSOCK), "-p", PORT, "-U", "serveroficina", "-d", db,
              "-v", "ON_ERROR_STOP=1", "-Atq", "-c", sql, check=check).stdout.strip()


def start_cluster():
    shutil.chown(PGROOT, "postgres", "postgres")
    PGSOCK.mkdir()
    shutil.chown(PGSOCK, "postgres", "postgres")
    run_pg = ["runuser", "-u", "postgres", "--"]
    sh(*run_pg, str(PGBIN / "initdb"), "-D", str(PGDATA), "-A", "trust", "-U", "postgres")
    sh(*run_pg, str(PGBIN / "pg_ctl"), "-D", str(PGDATA), "-w", "-l", str(PGROOT / "pg.log"),
       "-o", f"-k {PGSOCK} -p {PORT} -c listen_addresses=''", "start")
    sh(str(PGBIN / "psql"), "-h", str(PGSOCK), "-p", PORT, "-U", "postgres", "-d", "postgres", "-c",
       "CREATE ROLE serveroficina SUPERUSER LOGIN")


def stop_cluster():
    subprocess.run(["runuser", "-u", "postgres", "--", str(PGBIN / "pg_ctl"), "-D", str(PGDATA),
                    "-m", "immediate", "stop"], capture_output=True)
    shutil.rmtree(PGROOT, ignore_errors=True)


def write_stubs():
    BIN.mkdir(parents=True)
    stubs = {
        # docker exec [-i] server-oficina-postgres TOOL ARGS -> binario local contra el clúster del lab.
        # Como en Docker, stdin y stdout son tuberías (no posicionables): pg_restore lee el dump en secuencia.
        "docker": f'''#!/usr/bin/env bash
case "$1" in
  exec) shift; interactive=0; [[ "$1" == "-i" ]] && {{ interactive=1; shift; }}; shift; tool="$1"; shift
        if (( interactive )); then
          cat | "{PGBIN}/$tool" -h "{PGSOCK}" -p {PORT} "$@" | cat; exit "${{PIPESTATUS[1]}}"
        fi
        "{PGBIN}/$tool" -h "{PGSOCK}" -p {PORT} "$@" </dev/null | cat; exit "${{PIPESTATUS[0]}}" ;;
  inspect) exit 0 ;;
  *) exit 0 ;;
esac
''',
        "systemctl": '''#!/usr/bin/env bash
echo "systemctl $*" >> "$LAB_STATE/systemctl.log"
u="${!#}"
case "$1" in
  stop) echo inactive > "$LAB_STATE/$u.active" ;;
  start|restart) echo active > "$LAB_STATE/$u.active" ;;
  is-active) s=$(cat "$LAB_STATE/$u.active" 2>/dev/null || echo inactive); [[ "$2" == --quiet ]] || echo "$s"; [[ $s == active ]] ;;
esac
''',
        # Health real: falla si la base activa tiene la marca LAB_BREAK_HEALTH_ON.
        "curl": f'''#!/usr/bin/env bash
[[ "$(cat "$LAB_STATE/server-oficina.active" 2>/dev/null)" == active ]] || exit 7
marker=$("{PGBIN}/psql" -h "{PGSOCK}" -p {PORT} -U serveroficina -d server_oficina -Atq -c "select value from lab_marker" 2>/dev/null) || exit 7
[[ -n "${{LAB_BREAK_HEALTH_ON:-}}" && "$marker" == "$LAB_BREAK_HEALTH_ON" ]] && exit 7
[[ "${{LAB_BREAK_HEALTH_ALWAYS:-}}" == 1 ]] && exit 7
echo '{{"status":"ok","marker":"'"$marker"'"}}'
''',
        "sleep": "#!/bin/sh\nexit 0\n",
    }
    for name, body in stubs.items():
        (BIN / name).write_text(body)
        (BIN / name).chmod(0o755)


# ---------------------------------------------------------------- datos

def create_db_state(state: str, *, extra_table: bool = False, grant_role: str | None = None):
    """Estado reconocible: 'backup' (esquema viejo) o 'live' (esquema nuevo con tabla extra)."""
    psql("DROP DATABASE IF EXISTS server_oficina WITH (FORCE)", db="postgres")
    psql("CREATE DATABASE server_oficina", db="postgres")
    psql(f"""
        CREATE TABLE lab_marker (value text);
        INSERT INTO lab_marker VALUES ('{state}');
        CREATE TABLE projects (id int PRIMARY KEY, name text NOT NULL);
        CREATE TABLE documents (id int PRIMARY KEY, project_id int REFERENCES projects(id), body text);
        INSERT INTO projects SELECT g, '{state}-p' || g FROM generate_series(1, 200) g;
        INSERT INTO documents SELECT g, 1 + g % 200, repeat('{state}-', 200) FROM generate_series(1, 5000) g;
        CREATE INDEX documents_project ON documents(project_id);
    """)
    if extra_table:
        psql("CREATE TABLE newer_feature (id int PRIMARY KEY, project_id int REFERENCES projects(id));"
             "INSERT INTO newer_feature VALUES (1, 1);")
    if grant_role:
        psql(f"DROP ROLE IF EXISTS {grant_role}; CREATE ROLE {grant_role}; GRANT SELECT ON documents TO {grant_role};",
)


def db_fingerprint(db: str = "server_oficina") -> dict:
    tables = psql("select string_agg(table_name, ',' order by table_name) from information_schema.tables "
                  "where table_schema='public'", db=db)
    counts = {t: int(psql(f"select count(*) from {t}", db=db)) for t in tables.split(",") if t}
    return {"marker": psql("select value from lab_marker", db=db), "tables": counts}


def databases() -> list[str]:
    return psql("select datname from pg_database where not datistemplate order by 1", db="postgres").split("\n")


def make_backup(name: str, *, app_files: dict[str, bytes]) -> Path:
    dest = NS["/srv/server-oficina"] / "backups" / "server-oficina" / name
    dest.mkdir(parents=True)
    # Como backup.sh (docker exec ... pg_dump > archivo): el dump se escribe a través de una tubería.
    with open(dest / "database.dump", "wb") as out:
        subprocess.run(f'"{PGBIN}/pg_dump" -h "{PGSOCK}" -p {PORT} -U serveroficina -d server_oficina -Fc | cat',
                       shell=True, stdout=out, check=True)
    staging = LAB / f"app-{name}"
    for rel, data in app_files.items():
        (staging / rel).parent.mkdir(parents=True, exist_ok=True)
        (staging / rel).write_bytes(data)
    with tarfile.open(dest / "app-files.tar.gz", "w:gz") as tar:
        for top in ("imports", "evidence"):
            tar.add(staging / top, arcname=top)
    (dest / "VERSION").write_text("0.2.0-alpha.1\n")
    write_sums(dest)
    return dest


def write_sums(dest: Path):
    lines = [f"{hashlib.sha256((dest / f).read_bytes()).hexdigest()}  {f}\n"
             for f in sorted(p.name for p in dest.iterdir() if p.name != "SHA256SUMS")]
    (dest / "SHA256SUMS").write_text("".join(lines))


def set_live_app(files: dict[str, bytes]):
    app = NS["/srv/server-oficina"] / "data" / "app"
    shutil.rmtree(app, ignore_errors=True)
    for rel, data in files.items():
        (app / rel).parent.mkdir(parents=True, exist_ok=True)
        (app / rel).write_bytes(data)


def app_snapshot() -> dict[str, str]:
    app = NS["/srv/server-oficina"] / "data" / "app"
    return {p.relative_to(app).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(app.rglob("*")) if p.is_file() and not p.relative_to(app).parts[0].startswith(".")}


def run_restore(script: Path, backup: Path, name: str, **env_extra) -> subprocess.CompletedProcess:
    (STATE / "systemctl.log").write_text("")
    for unit in ("server-oficina", "server-oficina-local-cloud"):
        (STATE / f"{unit}.active").write_text("active\n")
    mounts = "\n".join(f'mkdir -p "{ns}" && mount --bind "{real}" "{ns}"' for ns, real in NS.items())
    ns_backup = "/srv/server-oficina/" + backup.relative_to(NS["/srv/server-oficina"]).as_posix()
    cmd = f"set -e\n{mounts}\nexec bash \"{script}\" \"{ns_backup}\"\n"
    env = {**os.environ, "PATH": f"{BIN}:{os.environ['PATH']}", "LAB_STATE": str(STATE), **env_extra}
    result = subprocess.run(["unshare", "--mount", "--propagation", "private", "bash", "-c", cmd],
                            env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=600)
    (LAB / f"{name}.log").write_text(result.stdout + "\n--- stderr ---\n" + result.stderr)
    LAST["stderr"] = result.stderr
    return result


LAST: dict = {}


def result_file() -> dict[str, str]:
    """Archivo de resultado que el script anunció en su última ejecución ("Resultado: <ruta>")."""
    lines = [l for l in LAST["stderr"].splitlines() if l.startswith("Resultado: /srv/server-oficina/")]
    if not lines:
        return {}
    real = NS["/srv/server-oficina"] / lines[-1].split("/srv/server-oficina/", 1)[1]
    return dict(line.split("=", 1) for line in real.read_text().splitlines())


def services() -> dict:
    return {u: (STATE / f"{u}.active").read_text().strip() for u in ("server-oficina", "server-oficina-local-cloud")}


def systemctl_log() -> list[str]:
    return (STATE / "systemctl.log").read_text().splitlines()


def check(name: str, condition: bool, detail: str = ""):
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def record(name: str, result: subprocess.CompletedProcess, **facts):
    entry = {"escenario": name, "exit": result.returncode, **facts}
    EVIDENCE["scenarios"].append(entry)
    print(f"RESTORE_LAB_STEP {json.dumps(entry, ensure_ascii=False)}", flush=True)


# ---------------------------------------------------------------- escenarios

def main() -> int:
    if os.geteuid() != 0:
        print("restore_lab requiere root (sudo -E)", file=sys.stderr)
        return 2
    if LAB.exists():
        shutil.rmtree(LAB)
    for path in [STATE, *NS.values()]:
        path.mkdir(parents=True)
    write_stubs()
    start_cluster()
    try:
        return scenarios()
    finally:
        (LAB / "evidence.json").write_text(json.dumps(EVIDENCE, indent=2, ensure_ascii=False))
        stop_cluster()


def reset_live(live_app: dict[str, bytes]):
    create_db_state("live", extra_table=True)
    set_live_app(live_app)


def scenarios() -> int:
    new_script = REPO / "scripts" / "restore.sh"
    old_script = LAB / "restore-anterior.sh"
    # Restore anterior (36a5ab8), tal cual, para reproducir el defecto. Como root en CI el
    # checkout pertenece a otro usuario: safe.directory explícito.
    old_script.write_text(sh("git", "-c", f"safe.directory={REPO}", "-C", str(REPO), "show",
                             "36a5ab8:scripts/restore.sh").stdout)

    backup_app = {"imports/lote.csv": b"a,b\n1,2\n", "evidence/foto.jpg": b"\xff\xd8backup"}
    live_app = {**backup_app, "evidence/foto.jpg": b"\xff\xd8modificada",
                "evidence/subida_despues_del_backup.pdf": b"%PDF extra"}

    # Respaldos de referencia.
    create_db_state("backup")
    ok = make_backup("20260927-010000", app_files=backup_app)
    truncated = make_backup("20260927-010001", app_files=backup_app)
    dump = truncated / "database.dump"
    dump.write_bytes(dump.read_bytes()[: int(dump.stat().st_size * 0.6)])
    write_sums(truncated)  # SHA coherente con el archivo truncado: sólo PostgreSQL puede detectarlo
    create_db_state("backup", grant_role="lab_reader")
    role_backup = make_backup("20260927-010002", app_files=backup_app)
    psql("REVOKE ALL ON documents FROM lab_reader; DROP ROLE lab_reader")  # el rol no existe al restaurar
    bad_sha = make_backup("20260927-010003", app_files=backup_app)
    with open(bad_sha / "database.dump", "r+b") as fh:
        fh.seek(200)
        fh.write(b"\x00\x00\x00\x00")

    # 0 · Defecto reproducido con el restore anterior: dump truncado deja la base viva parcial.
    reset_live(live_app)
    live_before = db_fingerprint()
    r = run_restore(old_script, truncated, "r0_anterior_dump_truncado")
    after = db_fingerprint()
    partial = after != live_before
    record("anterior_dump_truncado", r, base_viva_modificada=partial, base_despues=after,
           servicios=services(), anuncia_fallo_explicito="RESTORE_FAIL" in r.stderr)
    check("r0 reproduce el defecto", r.returncode != 0 and partial, f"{r.returncode} {after}")

    # 1 · Dump truncado con el restore nuevo: se detecta leyendo el dump entero,
    #     antes de crear ninguna base; servicios nunca detenidos.
    reset_live(live_app)
    live_before, app_before = db_fingerprint(), app_snapshot()
    r = run_restore(new_script, truncated, "r1_dump_truncado")
    check("r1", r.returncode == 20 and "RESTORE_FAIL" in r.stderr and "truncado" in r.stderr,
          f"exit={r.returncode} {r.stderr[-600:]}")
    check("r1 resultado", result_file().get("resultado") == "RESTORE_FAIL" and result_file().get("codigo") == "20",
          str(result_file()))
    check("r1 base intacta", db_fingerprint() == live_before and app_snapshot() == app_before)
    check("r1 servicios", services() == {"server-oficina": "active", "server-oficina-local-cloud": "active"}
          and not any(" stop " in f" {l} " for l in systemctl_log()), str(systemctl_log()))
    check("r1 sin bases temporales", databases() == ["postgres", "server_oficina"], str(databases()))
    record("dump_truncado_detectado_antes_de_tocar_nada", r, base_intacta=True, servicios=services(),
           bases=databases(), resultado=result_file())

    # 2 · Falla a mitad de la restauración (rol ausente al aplicar permisos).
    r = run_restore(new_script, role_backup, "r2_falla_a_mitad")
    check("r2", r.returncode == 21 and "RESTORE_FAIL" in r.stderr and "lab_reader" in r.stderr,
          f"exit={r.returncode} {r.stderr[-600:]}")
    check("r2 servicios", services() == {"server-oficina": "active", "server-oficina-local-cloud": "active"}
          and not any(" stop " in f" {l} " for l in systemctl_log()), str(systemctl_log()))
    check("r2 sin staging", not list((NS["/srv/server-oficina"] / "data" / "app").glob(".restore-staging-*")))
    check("r2 base intacta", db_fingerprint() == live_before and app_snapshot() == app_before)
    check("r2 sin bases temporales", databases() == ["postgres", "server_oficina"], str(databases()))
    check("r2 resultado propio", result_file().get("codigo") == "21", str(result_file()))
    logs = list((NS["/srv/server-oficina"] / "backups" / "restore-logs").glob("restore-*.txt"))
    check("r2 resultados no se pisan", len(logs) == 2, str(logs))
    record("pg_restore_falla_a_mitad_no_toca_base_viva", r, base_intacta=True, servicios=services(),
           bases=databases(), resultado=result_file())

    # 3b · tar dañado y tar con rutas fuera de imports/ y evidence/: nada se toca.
    for label, mutate in (("tar_truncado", "truncate"), ("tar_ruta_ajena", "escape")):
        bad = make_backup(f"20260927-01001{0 if mutate == 'truncate' else 1}", app_files=backup_app)
        tgz = bad / "app-files.tar.gz"
        if mutate == "truncate":
            tgz.write_bytes(tgz.read_bytes()[:-40])
        else:
            evil = LAB / "evil"
            (evil / "imports").mkdir(parents=True, exist_ok=True)
            (evil / "imports" / "a.csv").write_text("x")
            (evil / "config.env").write_text("SERVER_OFICINA_HOST=0.0.0.0\n")
            with tarfile.open(tgz, "w:gz") as tar:
                tar.add(evil / "imports", arcname="imports")
                tar.add(evil / "config.env", arcname="imports/../../../../etc/server-oficina/x.env")
        write_sums(bad)
        r = run_restore(new_script, bad, f"r3b_{label}")
        check(f"r3b {label}", r.returncode == 20 and db_fingerprint() == live_before and app_snapshot() == app_before
              and databases() == ["postgres", "server_oficina"], f"exit={r.returncode} {r.stderr[-400:]}")
        check(f"r3b {label} sin escape", not (NS["/etc/server-oficina"] / "x.env").exists())
        record(label, r, base_intacta=True, archivos_intactos=True)

    # 3 · SHA inválido: nada se toca.
    r = run_restore(new_script, bad_sha, "r3_sha_invalido")
    check("r3", r.returncode == 20 and db_fingerprint() == live_before, f"exit={r.returncode}")
    record("sha_invalido", r, base_intacta=True)

    # 4 · Health falla con la base restaurada: vuelta al estado previo completo.
    r = run_restore(new_script, ok, "r4_health_falla", LAB_BREAK_HEALTH_ON="backup")
    check("r4", r.returncode == 22 and "RESTORE_FAIL" in r.stderr, f"exit={r.returncode} {r.stderr[-800:]}")
    check("r4 base previa", db_fingerprint() == live_before, str(db_fingerprint()))
    check("r4 archivos previos", app_snapshot() == app_before, str(app_snapshot()))
    check("r4 servicios", services() == {"server-oficina": "active", "server-oficina-local-cloud": "active"})
    check("r4 sin residuos", databases() == ["postgres", "server_oficina"]
          and not [p.name for p in (NS["/srv/server-oficina"] / "data" / "app").iterdir() if p.name.startswith(".")],
          f"{databases()} {list((NS['/srv/server-oficina'] / 'data' / 'app').iterdir())}")
    check("r4 resultado", result_file().get("codigo") == "22" and result_file().get("base_previa") == "ninguna",
          str(result_file()))
    record("health_falla_revierte_todo", r, base_previa_restablecida=True, archivos_previos=True,
           servicios=services(), bases=databases())

    # 4b · La API tampoco responde tras revertir: datos previos restablecidos,
    #      servicios detenidos a propósito, fallo crítico explícito.
    r = run_restore(new_script, ok, "r4b_health_falla_siempre", LAB_BREAK_HEALTH_ALWAYS="1")
    check("r4b", r.returncode == 23 and "RESTORE_FAIL_CRITICO" in r.stderr and "RESTORE_OK" not in r.stdout,
          f"exit={r.returncode} {r.stderr[-800:]}")
    check("r4b datos previos", db_fingerprint() == live_before and app_snapshot() == app_before)
    check("r4b servicios detenidos", services() == {"server-oficina": "inactive", "server-oficina-local-cloud": "inactive"},
          str(services()))
    check("r4b sin residuos", databases() == ["postgres", "server_oficina"], str(databases()))
    record("health_falla_siempre_critico_servicios_detenidos", r, datos_previos=True, servicios=services(),
           resultado=result_file())

    # 5 · Restauración correcta de un esquema más antiguo con archivos extra.
    reset_live(live_app)
    psql("select 1", db="postgres")
    for extra in [d for d in databases() if d not in ("postgres", "server_oficina")]:
        psql(f"DROP DATABASE {extra}", db="postgres")
    r = run_restore(new_script, ok, "r5_ok")
    restored = db_fingerprint()
    previous_dbs = [d for d in databases() if d.startswith("server_oficina_pre_restore_")]
    app_dir = NS["/srv/server-oficina"] / "data" / "app"
    kept = list(app_dir.glob(".pre-restore-*/evidence/subida_despues_del_backup.pdf"))
    check("r5", r.returncode == 0 and "RESTORE_OK" in r.stdout, f"exit={r.returncode} {r.stderr[-800:]}")
    check("r5 base = respaldo", restored["marker"] == "backup" and "newer_feature" not in restored["tables"],
          str(restored))
    check("r5 base previa conservada", len(previous_dbs) == 1
          and db_fingerprint(previous_dbs[0]) == live_before, str(previous_dbs))
    check("r5 archivos = respaldo", app_snapshot() == {k: hashlib.sha256(v).hexdigest() for k, v in backup_app.items()},
          str(app_snapshot()))
    check("r5 extra conservado", len(kept) == 1 and kept[0].read_bytes() == b"%PDF extra")
    diff = (kept[0].parents[1] / "DIFERENCIAS_CON_RESPALDO.tsv").read_text().splitlines()
    check("r5 diferencias", diff == ["distinto_en_respaldo\tevidence/foto.jpg",
                                     "ausente_en_respaldo\tevidence/subida_despues_del_backup.pdf"], str(diff))
    check("r5 resultado", result_file().get("resultado") == "RESTORE_OK"
          and result_file().get("base_previa") == previous_dbs[0], str(result_file()))
    check("r5 servicios", services() == {"server-oficina": "active", "server-oficina-local-cloud": "active"})
    record("restore_correcto_esquema_antiguo", r, base_restaurada=restored["marker"],
           base_previa_conservada=previous_dbs[0], archivo_extra_conservado=kept[0].name,
           diferencias=diff, servicios=services(), resultado=result_file())

    EVIDENCE["result"] = "RESTORE_LAB_OK"
    print("RESTORE_LAB_OK", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - toda falla del laboratorio queda como evidencia
        EVIDENCE["result"] = f"FAIL: {exc.__class__.__name__}: {exc}"
        (LAB / "evidence.json").write_text(json.dumps(EVIDENCE, indent=2, ensure_ascii=False))
        print(f"RESTORE_LAB_FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
