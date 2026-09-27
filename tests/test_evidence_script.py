"""scripts/evidencia-latitude.sh: la evidencia PRE/POST no oculta resultados ni imprime secretos.

Origen (PRE real de la Latitude, 2026-09-27): ``lan_firewall.py audit`` encontró un
problema (salida 5) y el script lo encadenaba con ``||``, de modo que el archivo
mostraba el JSON seguido de "auditoría LAN no disponible" y ``[rc=0]``.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "scripts" / "evidencia-latitude.sh").read_text(encoding="utf-8")


def _audit_block(tmp_path: Path, current_has_fw: bool, src_exit: int | None) -> str:
    """Ejecuta run() y el bloque real de auditoría del script con releases simuladas."""
    run_fn = re.search(r"^run\(\) \{.*?^\}", SCRIPT, re.S | re.M).group(0)
    block = SCRIPT.split("# >>> auditoria-lan", 1)[1].split("# <<< auditoria-lan", 1)[0]
    current, src = tmp_path / "current", tmp_path / "src"
    (current / "scripts").mkdir(parents=True)
    (src / "scripts").mkdir(parents=True)
    fake = 'import sys\nprint("LAN_AUDIT {}")\nsys.exit(%d)\n'
    if current_has_fw:
        (current / "scripts" / "lan_firewall.py").write_text(fake % 0)
    if src_exit is not None:
        (src / "scripts" / "lan_firewall.py").write_text(fake % src_exit)
    script = f'CURRENT="{current}"; SRC="{src}"\n{run_fn}\n{block}\n'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout


def test_audit_problems_are_reported_with_their_exit_code(tmp_path: Path):
    out = _audit_block(tmp_path, current_has_fw=False, src_exit=5)  # alpha.3 + candidata con problemas
    assert "LAN_AUDIT" in out and "[rc=5]" in out
    assert "no disponible" not in out
    assert f"reconciliador usado: {tmp_path / 'src'}" in out


def test_active_release_reconciler_is_preferred(tmp_path: Path):
    out = _audit_block(tmp_path, current_has_fw=True, src_exit=5)
    assert f"reconciliador usado: {tmp_path / 'current'}" in out and "[rc=0]" in out


def test_audit_unavailable_only_when_no_reconciler_exists(tmp_path: Path):
    out = _audit_block(tmp_path, current_has_fw=False, src_exit=None)
    assert "auditoría LAN no disponible" in out and "LAN_AUDIT" not in out


def test_no_command_masks_the_audit_exit_code():
    assert not re.search(r"lan_firewall\.py audit[^\n]*\|\|", SCRIPT)


def test_evidence_never_prints_secrets():
    code = "\n".join(l for l in SCRIPT.splitlines() if not l.lstrip().startswith("#"))
    for line in code.splitlines():
        if "server-oficina.env" in line and "ls -la" not in line:
            # Sólo el volcado redactado o una lista cerrada de claves no secretas.
            assert "<redactado>" in line or "grep -E '^SERVER_OFICINA_(" in line, line
            assert not re.search(r"DATABASE_URL|API_KEY|PASSWORD|TOKEN|SECRET", line.split("<redactado>")[0]), line
    assert not re.search(r"cat [^\n]*postgres_password", code)
    assert "--show-secrets" not in code and "psk=" not in code


def test_pre_install_checks_are_collected():
    for marker in ("COMPOSE_RECREA_POSTGRES", "config --hash postgres", "https://pypi.org/simple/pip/",
                   "secrets/postgres_password", "query_to_xml", "psk-flags", "dispatcher.d",
                   "journalctl -b -u avahi-daemon", "avahi-resolve -4 -n server-oficina.local"):
        assert marker in SCRIPT, marker
