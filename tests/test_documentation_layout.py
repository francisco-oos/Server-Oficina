from pathlib import Path
import re


def test_docs_root_stays_small_and_categorized():
    root = Path("docs")
    root_files = sorted(p.name for p in root.glob("*.md"))
    assert root_files == ["00_INDICE_DOCUMENTACION.md", "INICIO_RAPIDO.md", "README.md"]
    expected = {"vision", "arquitectura", "decisiones", "investigacion", "dominios", "interfaz", "seguridad", "pruebas", "operacion", "desarrollo", "estado"}
    actual = {p.name for p in root.iterdir() if p.is_dir()}
    assert expected.issubset(actual)


def test_documentation_index_points_to_existing_files():
    root = Path("docs")
    text = (root / "00_INDICE_DOCUMENTACION.md").read_text(encoding="utf-8")
    pattern = r"`((?:vision|arquitectura|decisiones|investigacion|dominios|interfaz|seguridad|pruebas|operacion|desarrollo|estado)/[^`]+[.]md)`"
    refs = re.findall(pattern, text)
    assert refs
    missing = [ref for ref in refs if not (root / ref).is_file()]
    assert missing == []
