"""Los workflows de CI se disparan en ramas de agentes y PRs sin abrir superficie peligrosa."""

import re
from pathlib import Path

WORKFLOWS = sorted((Path(__file__).resolve().parents[1] / ".github" / "workflows").glob("*.yml"))


def _code(workflow: Path) -> str:
    """Contenido sin líneas de comentario (los comentarios pueden nombrar lo prohibido)."""
    return "\n".join(l for l in workflow.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))


def test_workflows_exist():
    names = {w.name for w in WORKFLOWS}
    assert {"local-cloud-ci.yml", "syncthing-integration.yml", "installer-lab.yml"} <= names


def test_no_privileged_triggers_and_read_only_token():
    for workflow in WORKFLOWS:
        text = _code(workflow) + "\n"
        assert "pull_request_target" not in text, workflow.name
        assert "workflow_run" not in text, workflow.name
        assert re.search(r"^permissions:\n  contents: read\n", text, re.M), workflow.name
        assert "secrets." not in text, workflow.name


def test_integration_branches_trigger_every_gate():
    for workflow in WORKFLOWS:
        text = workflow.read_text(encoding="utf-8")
        push = text.split("push:", 1)[1].split("pull_request", 1)[0]
        assert '"claude/**"' in push and '"agent/**"' in push, workflow.name
        assert "workflow_dispatch:" in text, workflow.name
