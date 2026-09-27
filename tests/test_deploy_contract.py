"""Contrato entre unidades systemd, instalador y configuración.

Origen: ``server-oficina-local-cloud.service`` declaraba ``ReadWritePaths`` que
el instalador no creaba (systemd no arranca una unidad cuyo ReadWritePaths no
existe), el env no fijaba ``SERVER_OFICINA_VERSIONS_ROOT`` (el ContentStore
caía en ``data/app/versions``) y la unidad ni siquiera se instalaba. Además la
release se nombraba sólo por VERSION, de modo que reinstalar la misma VERSION
sobrescribía en caliente el código activo y anulaba el rollback.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "scripts" / "install-tablet.sh").read_text(encoding="utf-8")
LIB = ROOT / "scripts" / "lib-release.sh"


def _unit_directives(name: str, key: str) -> list[str]:
    values: list[str] = []
    for line in (ROOT / "deploy" / name).read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            values.extend(line.split("=", 1)[1].split())
    return values


def _installer_vars() -> dict[str, str]:
    values: dict[str, str] = {}
    for name, raw in re.findall(r"^([A-Z_]+)=([^\s$(][^\s]*|\$[A-Z_]+/[^\s]+)$", INSTALLER, re.M):
        values[name] = re.sub(r"\$([A-Z_]+)", lambda m: values.get(m.group(1), m.group(0)), raw)
    return values


def _created_dirs() -> set[str]:
    variables = _installer_vars()
    created: set[str] = set()
    mkdir = re.search(r'mkdir -p .*"\$DATA"/\{([^}]*)\}', INSTALLER)
    assert mkdir, "el instalador debe crear la estructura base de /srv"
    created |= {f"{variables['DATA']}/{part}" for part in mkdir.group(1).split(",")}
    for token in re.findall(r'^\s*install -d .*"\$([A-Z_]+)"$', INSTALLER, re.M):
        created.add(variables[token])
    return created


def test_every_readwrite_path_is_created_by_the_installer():
    created = _created_dirs()
    for unit in sorted((ROOT / "deploy").glob("*.service")):
        for path in _unit_directives(unit.name, "ReadWritePaths"):
            if path.startswith("-"):
                continue
            assert path in created, f"{unit.name}: {path} no lo crea install-tablet.sh"


def test_every_unit_is_installed():
    variables = _installer_vars()
    installed = set(re.findall(r'deploy/([\w.$-]+\.(?:service|timer))"', INSTALLER))
    installed = {re.sub(r"\$([A-Z_]+)", lambda m: variables[m.group(1)], x) for x in installed}
    units = {p.name for p in (ROOT / "deploy").iterdir() if p.suffix in {".service", ".timer"}}
    assert units <= installed, units - installed


def test_env_points_content_store_to_the_writable_path_of_the_observer():
    variables = _installer_vars()
    env = dict(re.findall(r"^(SERVER_OFICINA_[A-Z_]+)=(.*)$", INSTALLER, re.M))
    resolve = lambda raw: re.sub(r"\$([A-Z_]+)", lambda m: variables[m.group(1)], raw)
    versions_root = resolve(env["SERVER_OFICINA_VERSIONS_ROOT"])
    sync_root = resolve(env["SERVER_OFICINA_SYNC_ROOT"])
    writable = _unit_directives("server-oficina-local-cloud.service", "ReadWritePaths")
    assert versions_root in writable
    # Las carpetas sincronizadas son de sólo lectura para el observador.
    assert sync_root not in writable
    assert _unit_directives("server-oficina-local-cloud.service", "ProtectSystem") == ["strict"]


def test_installer_never_overwrites_an_existing_release():
    assert "releases/$VERSION" not in INSTALLER
    guard = INSTALLER.index("assert_new_release")
    promote = INSTALLER.index('swap_current "$RELEASE"')
    assert guard < INSTALLER.index("rsync ") < promote
    assert "--delete" not in INSTALLER.split("rsync ", 1)[1].split("\n", 1)[0]
    # Respaldo pre-upgrade siempre antes de promover; `current` se cambia de forma atómica.
    assert INSTALLER.index("PRE_UPGRADE_BACKUP_OK") < promote
    assert 'mv -Tf "$CURRENT.new" "$CURRENT"' in INSTALLER
    assert 'ln -sfn "$RELEASE" "$CURRENT"' not in INSTALLER


def test_release_code_is_owned_by_root_not_by_the_checkout_owner():
    rsync = INSTALLER.split("\nrsync ", 1)[1].split("\n", 1)[0]
    assert "--chown=root:root" in rsync and "--chmod=Dgo-w,Fgo-w" in rsync


def test_permission_model_least_privilege():
    variables = _installer_vars()
    files, versions = variables["FILES"], variables["VERSIONS"]
    assert re.search(r'install -d -o root -g "\$SERVICE_GROUP" -m 2750 "\$FILES"', INSTALLER)
    assert re.search(r'install -d -o "\$SERVICE_USER" -g "\$SERVICE_GROUP" -m 2750 "\$VERSIONS"', INSTALLER)
    # Observador: sólo versions/ escribible.
    assert _unit_directives("server-oficina-local-cloud.service", "ReadWritePaths") == [versions]
    # API: no escribe archivos sincronizados ni historial.
    read_only = _unit_directives("server-oficina.service", "ReadOnlyPaths")
    assert f"-{files}" in read_only and f"-{versions}" in read_only


def _bash(script: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", f'source "{LIB}"; {script}'],
        capture_output=True, text=True, cwd=cwd,
    )


def test_release_id_includes_version_stamp_and_commit(tmp_path: Path):
    if not shutil.which("git"):
        pytest.skip("git no disponible")
    (tmp_path / "VERSION").write_text("0.2.0-alpha.1\n", encoding="utf-8")
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(tmp_path)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "VERSION"], check=True)
    subprocess.run([*git, "commit", "-qm", "v"], check=True)

    clean = _bash(f'release_id "{tmp_path}" 20260927-101500')
    assert clean.returncode == 0, clean.stderr
    assert re.fullmatch(r"0\.2\.0-alpha\.1\+20260927-101500\.g[0-9a-f]{12}\n", clean.stdout)

    (tmp_path / "VERSION").write_text("0.2.0-alpha.1\n\n", encoding="utf-8")
    dirty = _bash(f'release_id "{tmp_path}" 20260927-101501')
    assert dirty.stdout.strip().endswith(".dirty")


def test_release_id_outside_git_and_invalid_input(tmp_path: Path):
    (tmp_path / "VERSION").write_text("0.2.0-alpha.1", encoding="utf-8")
    plain = _bash(f'GIT_CEILING_DIRECTORIES="{tmp_path.parent}" release_id "{tmp_path}" 20260927-101500')
    assert plain.stdout.strip() == "0.2.0-alpha.1+20260927-101500"

    (tmp_path / "VERSION").write_text("../../etc", encoding="utf-8")
    assert _bash(f'release_id "{tmp_path}" 20260927-101500').returncode != 0
    (tmp_path / "VERSION").write_text("0.2.0", encoding="utf-8")
    assert _bash(f'release_id "{tmp_path}" hoy').returncode != 0


def test_assert_new_release_refuses_active_or_existing_release(tmp_path: Path):
    releases = tmp_path / "releases"
    active = releases / "0.2.0-alpha.1"
    active.mkdir(parents=True)
    current = tmp_path / "current"
    current.symlink_to(active)

    same = _bash(f'assert_new_release "{active}" "{active.resolve()}"')
    assert same.returncode != 0 and "activa" in same.stderr
    via_link = _bash(f'assert_new_release "{current}" "{active.resolve()}"')
    assert via_link.returncode != 0

    other = releases / "0.2.0-alpha.1+20260101-000000"
    other.mkdir()
    existing = _bash(f'assert_new_release "{other}" "{active.resolve()}"')
    assert existing.returncode != 0 and "ya existe" in existing.stderr

    fresh = _bash(f'assert_new_release "{releases / "0.2.0-alpha.1+20260927-101500"}" "{active.resolve()}"')
    assert fresh.returncode == 0, fresh.stderr
    first_install = _bash(f'assert_new_release "{releases / "nueva"}" ""')
    assert first_install.returncode == 0


def test_manifest_check_detects_unlisted_changed_and_missing_files(tmp_path: Path):
    tree = tmp_path / "pkg"
    (tree / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "generate-manifest.sh", tree / "scripts" / "generate-manifest.sh")
    (tree / "a.txt").write_text("a", encoding="utf-8")
    (tree / ".env").write_text("SECRETO=1", encoding="utf-8")
    run = lambda *args: subprocess.run(
        ["bash", str(tree / "scripts" / "generate-manifest.sh"), *args], capture_output=True, text=True
    )

    assert run().returncode == 0
    manifest = (tree / "MANIFEST.sha256").read_text(encoding="utf-8")
    assert ".env" not in manifest, "un secreto local no debe entrar al manifiesto"
    assert run("--check").returncode == 0

    (tree / "RELEASE_INFO").write_text("release_id=x", encoding="utf-8")
    assert run("--check").returncode == 0

    (tree / "extra.txt").write_text("no listado", encoding="utf-8")
    assert run("--check").returncode != 0
    (tree / "extra.txt").unlink()

    (tree / "a.txt").write_text("cambiado", encoding="utf-8")
    assert run("--check").returncode != 0
    (tree / "a.txt").unlink()
    assert run("--check").returncode != 0


def test_lan_firewall_units_are_installed_and_point_to_the_reconciler():
    script = (ROOT / "scripts" / "configurar-acceso-lan.sh").read_text(encoding="utf-8")
    for name in ("server-oficina-lan-firewall.service", "server-oficina-lan-firewall.timer",
                 "90-server-oficina-lan"):
        assert (ROOT / "deploy" / "lan-firewall" / name).is_file()
        assert f"deploy/lan-firewall/{name}" in script
    unit = (ROOT / "deploy" / "lan-firewall" / "server-oficina-lan-firewall.service").read_text(encoding="utf-8")
    assert "/opt/server-oficina/current/scripts/lan_firewall.py apply" in unit
    # Nunca una regla abierta a cualquier origen ni fijada a una subred concreta.
    assert "allow" not in script.replace("lan_firewall.py", "")
    assert not re.search(r"\d+\.\d+\.\d+\.\d+/\d+", script)
