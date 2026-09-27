#!/usr/bin/env python3
from __future__ import annotations

"""Laboratorio nativo: Syncthing real + observador Server Oficina en el hub.

Complementa ``syncthing_smoke.py`` (que sólo valida transporte): aquí el
observador real (``python -m app.workers.local_cloud_worker``) vigila la carpeta
del hub mientras tres procesos Syncthing (pc1 ↔ hub ↔ pc2) replican cambios, y
se verifica que Server Oficina registre versiones, tombstones, recuperaciones y
conflictos con SHA-256 idéntico y copia en el ContentStore.

NO equivale al gate físico: todo corre en un solo host, por loopback, sin
Windows, sin Wi-Fi y sin Office. Sirve para no llevar a la Latitude defectos
que ya pueden reproducirse aquí.

Uso:
    SYNCTHING_BIN=/ruta/syncthing LAB_ROOT=/tmp/lab python tests/integration/hub_worker_lab.py

Escribe un resumen JSON en ``$LAB_ROOT/evidence.json``.
"""

import hashlib
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[2]
BIN = os.environ.get("SYNCTHING_BIN") or shutil.which("syncthing")
ROOT = Path(os.environ.get("LAB_ROOT", "runtime/hub-worker-lab")).resolve()
API_KEY = "server-oficina-lab"
FOLDER = "lab-sync"
NODES = {
    "hub": {"gui": 28384, "listen": 22100},
    "pc1": {"gui": 28385, "listen": 22101},
    "pc2": {"gui": 28386, "listen": 22102},
}
HUB_FILES = ROOT / "hub" / "files"
HUB_SHARE = HUB_FILES / "LAB_SYNC"
VERSIONS = ROOT / "hub" / "versions"
DB = ROOT / "server_oficina_lab.db"
PROCS: dict[str, subprocess.Popen] = {}
EVIDENCE: dict = {"steps": [], "files": {}}


def folder_path(node: str) -> Path:
    return HUB_SHARE if node == "hub" else ROOT / node / "LAB_SYNC"


def request(node: str, method: str, path: str, *, params=None, payload=None):
    query = "?" + urlencode(params) if params else ""
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(
        f"http://127.0.0.1:{NODES[node]['gui']}{path}{query}", data=data, method=method,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
    )
    with urlopen(req, timeout=10) as response:
        body = response.read()
        return json.loads(body) if body else None


def wait_until(label: str, predicate, timeout: float = 90.0, interval: float = 0.5):
    started = time.monotonic()
    last = None
    while time.monotonic() - started < timeout:
        try:
            last = predicate()
            if last:
                return time.monotonic() - started
        except Exception as exc:  # noqa: BLE001 - diagnóstico del laboratorio
            last = repr(exc)
        time.sleep(interval)
    raise AssertionError(f"Timeout esperando {label}; último={last!r}")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def step(name: str, **details):
    EVIDENCE["steps"].append({"step": name, **details})
    print(f"LAB_STEP {name} {json.dumps(details, ensure_ascii=False)}", flush=True)


# ---------------------------------------------------------------- Syncthing

def generate(node: str):
    home = ROOT / f"{node}-home"
    subprocess.run([BIN, "generate", f"--home={home}", "--no-port-probing"], check=True,
                   stdout=subprocess.DEVNULL)
    tree = ET.parse(home / "config.xml")
    options = tree.getroot().find("options")
    for tag, value in {
        "globalAnnounceEnabled": "false", "localAnnounceEnabled": "false",
        "relaysEnabled": "false", "natEnabled": "false", "startBrowser": "false",
        "crashReportingEnabled": "false", "urAccepted": "-1", "autoUpgradeIntervalH": "0",
    }.items():
        element = options.find(tag)
        if element is None:
            element = ET.SubElement(options, tag)
        element.text = value
    for element in options.findall("listenAddress"):
        options.remove(element)
    ET.SubElement(options, "listenAddress").text = f"tcp://127.0.0.1:{NODES[node]['listen']}"
    tree.write(home / "config.xml")


def start(node: str):
    home = ROOT / f"{node}-home"
    log = open(ROOT / f"{node}.log", "ab")
    PROCS[node] = subprocess.Popen(
        [BIN, "serve", f"--home={home}", f"--gui-address=127.0.0.1:{NODES[node]['gui']}",
         f"--gui-apikey={API_KEY}", "--no-browser", "--no-upgrade", "--no-restart"],
        stdout=log, stderr=subprocess.STDOUT,
    )
    wait_until(f"API {node}", lambda: request(node, "GET", "/rest/system/status"), timeout=60)


def stop(node: str):
    proc = PROCS.pop(node, None)
    if proc and proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def scan(node: str):
    request(node, "POST", "/rest/db/scan", params={"folder": FOLDER})


def configure() -> dict[str, str]:
    ids = {n: request(n, "GET", "/rest/system/status")["myID"] for n in NODES}
    peers = {"hub": ("pc1", "pc2"), "pc1": ("hub",), "pc2": ("hub",)}
    for node, others in peers.items():
        for peer in others:
            request(node, "POST", "/rest/config/devices", payload={
                "deviceID": ids[peer], "name": peer,
                "addresses": [f"tcp://127.0.0.1:{NODES[peer]['listen']}"],
                "introducer": False, "autoAcceptFolders": False,
            })
    for node, others in peers.items():
        folder_path(node).mkdir(parents=True, exist_ok=True)
        request(node, "POST", "/rest/config/folders", payload={
            "id": FOLDER, "label": "LAB_SYNC", "path": str(folder_path(node)),
            "type": "sendreceive", "devices": [{"deviceID": ids[p]} for p in others],
            "rescanIntervalS": 3600, "fsWatcherEnabled": True, "fsWatcherDelayS": 1,
            "ignorePerms": True, "maxConflicts": -1,
            "versioning": {"type": "staggered", "params": {"maxAge": "31536000"}},
        })

    def connected():
        conns = request("hub", "GET", "/rest/system/connections")["connections"]
        return all(conns.get(ids[p], {}).get("connected") for p in ("pc1", "pc2"))

    wait_until("pc1 y pc2 conectadas al hub", connected)
    return ids


# ---------------------------------------------------------- Server Oficina

def so_env() -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(REPO),
        "PYTHONDONTWRITEBYTECODE": "1",
        "SERVER_OFICINA_ENV": "lab",
        "SERVER_OFICINA_DATABASE_URL": f"sqlite+pysqlite:///{DB}",
        "SERVER_OFICINA_DATA_DIR": str(ROOT / "hub" / "data"),
        "SERVER_OFICINA_SYNC_ROOT": str(HUB_FILES),
        "SERVER_OFICINA_VERSIONS_ROOT": str(VERSIONS),
        # Atribución técnica de dispositivo vía la API real del Syncthing del hub.
        "SERVER_OFICINA_SYNCTHING_API": f"http://127.0.0.1:{NODES['hub']['gui']}",
        "SERVER_OFICINA_SYNCTHING_API_KEY": API_KEY,
    }


def prepare_server_oficina(ids: dict[str, str]):
    code = f"""
from app.db.base import Base, SessionLocal, engine
from app.db import models as _models  # noqa: F401 -- mismo esquema que app.main
from app.db import local_cloud_models as m
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    db.add(m.SyncShare(code="LAB_SYNC", name="LAB", owner_area_code="LAB",
                       local_root={str(HUB_SHARE)!r}, syncthing_folder_id={FOLDER!r}))
    db.add(m.SyncPeer(code="LAB-PC1", display_name="PC1 laboratorio", platform="linux-lab",
                      syncthing_device_id={ids["pc1"]!r}))
    db.add(m.SyncPeer(code="LAB-PC2", display_name="PC2 laboratorio", platform="linux-lab",
                      syncthing_device_id={ids["pc2"]!r}))
    db.commit()
"""
    subprocess.run([sys.executable, "-c", code], check=True, env=so_env(), cwd=REPO)


def start_worker():
    log = open(ROOT / "worker.log", "ab")
    PROCS["worker"] = subprocess.Popen(
        [sys.executable, "-m", "app.workers.local_cloud_worker", "--interval", "2", "--settle", "1"],
        env=so_env(), cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
    )


def rows(sql: str, *args):
    with sqlite3.connect(DB, timeout=10) as conn:
        return conn.execute(sql, args).fetchall()


def versions(path: str) -> list[tuple[str, str]]:
    return rows(
        "SELECT v.change_kind, v.sha256 FROM document_versions v "
        "JOIN document_records d ON d.id = v.document_id "
        "WHERE d.logical_path = ? ORDER BY v.observed_at", path,
    )


def wait_versions(path: str, expected: list[tuple[str, str]], timeout: float = 60.0) -> float:
    return wait_until(f"versiones {path}={expected}", lambda: versions(path) == expected, timeout=timeout)


def stored(digest: str) -> bool:
    target = VERSIONS / "sha256" / digest[:2] / digest
    return target.is_file() and sha(target.read_bytes()) == digest


def write(node: str, relative: str, data: bytes, *, mtime_ns: int | None = None):
    target = folder_path(node) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.parent / f".lab-write-{time.time_ns()}.tmp"
    temp.write_bytes(data)
    if mtime_ns is not None:
        os.utime(temp, ns=(mtime_ns, mtime_ns))
    os.replace(temp, target)
    scan(node)


def wait_file(node: str, relative: str, data: bytes | None) -> float:
    path = folder_path(node) / relative
    if data is None:
        return wait_until(f"{relative} ausente en {node}", lambda: not path.exists())
    return wait_until(f"{relative} en {node}", lambda: path.is_file() and path.read_bytes() == data)


def synthetic_xlsx(label: str) -> bytes:
    from io import BytesIO

    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "LAB"
    sheet.append(["codigo", "descripcion", "cantidad"])
    sheet.append(["LAB-001", f"Registro sintético {label}", 1])
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def proc_usage(pid: int) -> dict:
    status = Path(f"/proc/{pid}/status").read_text()
    rss_kb = int(next(line.split()[1] for line in status.splitlines() if line.startswith("VmRSS:")))
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    ticks = int(fields[11]) + int(fields[12])
    return {"rss_mib": round(rss_kb / 1024, 1), "cpu_s": round(ticks / os.sysconf("SC_CLK_TCK"), 2)}


# -------------------------------------------------------------- escenarios

def run():
    xlsx_v1 = synthetic_xlsx("v1")
    write("pc1", "Inventario_LAB.xlsx", xlsx_v1)
    step("crear", archivo="Inventario_LAB.xlsx", sha256=sha(xlsx_v1),
         hub_s=round(wait_file("hub", "Inventario_LAB.xlsx", xlsx_v1), 2),
         registro_s=round(wait_versions("Inventario_LAB.xlsx", [("MODIFIED", sha(xlsx_v1))]), 2),
         content_store=stored(sha(xlsx_v1)))

    xlsx_v2 = synthetic_xlsx("v2")
    write("pc1", "Inventario_LAB.xlsx", xlsx_v2)
    wait_file("hub", "Inventario_LAB.xlsx", xlsx_v2)
    wait_versions("Inventario_LAB.xlsx", [("MODIFIED", sha(xlsx_v1)), ("MODIFIED", sha(xlsx_v2))])
    step("modificar", sha256_v2=sha(xlsx_v2), v1_conservada=stored(sha(xlsx_v1)), v2=stored(sha(xlsx_v2)))

    doc = b"Documento LAB sintetico\n" * 64
    write("pc1", "Nota_LAB.txt", doc)
    wait_versions("Nota_LAB.txt", [("MODIFIED", sha(doc))])
    (folder_path("pc1") / "Nota_LAB.txt").rename(folder_path("pc1") / "Nota_LAB_renombrada.txt")
    scan("pc1")
    wait_file("hub", "Nota_LAB.txt", None)
    wait_file("hub", "Nota_LAB_renombrada.txt", doc)
    wait_versions("Nota_LAB.txt", [("MODIFIED", sha(doc)), ("DELETED", sha(doc))])
    wait_versions("Nota_LAB_renombrada.txt", [("MODIFIED", sha(doc))])
    step("renombrar", modelo="tombstone(origen) + documento nuevo(destino); mismo SHA", sha256=sha(doc))

    (folder_path("pc1") / "Subcarpeta").mkdir()
    (folder_path("pc1") / "Nota_LAB_renombrada.txt").rename(folder_path("pc1") / "Subcarpeta" / "Nota_LAB_movida.txt")
    scan("pc1")
    wait_file("hub", "Subcarpeta/Nota_LAB_movida.txt", doc)
    wait_versions("Subcarpeta/Nota_LAB_movida.txt", [("MODIFIED", sha(doc))])
    wait_versions("Nota_LAB_renombrada.txt", [("MODIFIED", sha(doc)), ("DELETED", sha(doc))])
    step("mover", destino="Subcarpeta/Nota_LAB_movida.txt")

    binary = os.urandom(3 * 1024 * 1024 + 17)
    write("pc1", "Binario_LAB.bin", binary)
    wait_file("hub", "Binario_LAB.bin", binary)
    wait_versions("Binario_LAB.bin", [("MODIFIED", sha(binary))])
    original_mtime = (folder_path("pc1") / "Binario_LAB.bin").stat().st_mtime_ns
    (folder_path("pc1") / "Binario_LAB.bin").unlink()
    scan("pc1")
    wait_file("hub", "Binario_LAB.bin", None)
    wait_versions("Binario_LAB.bin", [("MODIFIED", sha(binary)), ("DELETED", sha(binary))])
    stversions = any("Binario_LAB" in p.name for p in (HUB_SHARE / ".stversions").rglob("*"))
    step("borrar", sha256=sha(binary), content_store_conserva=stored(sha(binary)), hub_stversions=stversions)

    # Papelera de Windows / .stversions restauran bytes y mtime originales.
    write("pc1", "Binario_LAB.bin", binary, mtime_ns=original_mtime)
    wait_file("hub", "Binario_LAB.bin", binary)
    wait_versions("Binario_LAB.bin", [("MODIFIED", sha(binary)), ("DELETED", sha(binary)), ("RECOVERED", sha(binary))])
    live = rows("SELECT deleted FROM document_records WHERE logical_path='Binario_LAB.bin'")
    step("restaurar_mismo_mtime", documento_vivo=live == [(0,)])

    # Restore desde el historial de Server Oficina hacia la carpeta del hub.
    subprocess.run([sys.executable, "-c", (
        "from pathlib import Path\n"
        "from app.services.content_store import ContentStore\n"
        f"ContentStore(Path({str(VERSIONS)!r})).restore_to({sha(xlsx_v1)!r}, "
        f"Path({str(HUB_SHARE / 'Inventario_LAB_restaurado_v1.xlsx')!r}))\n"
    )], check=True, env=so_env(), cwd=REPO)
    scan("hub")
    step("restore_desde_historial", pc1_s=round(wait_file("pc1", "Inventario_LAB_restaurado_v1.xlsx", xlsx_v1), 2),
         sha256=sha(xlsx_v1))

    stop("hub")
    offline = b"creado con hub apagado\n"
    write("pc1", "Offline_hub.txt", offline)
    time.sleep(2)
    start("hub")
    step("reinicio_hub_con_cambio_pendiente",
         convergencia_s=round(wait_file("hub", "Offline_hub.txt", offline), 2),
         registro_s=round(wait_versions("Offline_hub.txt", [("MODIFIED", sha(offline))]), 2))

    stop("pc1")
    start("pc1")
    after_pc = b"tras reinicio de pc1\n"
    write("pc1", "Tras_reinicio_pc1.txt", after_pc)
    wait_file("hub", "Tras_reinicio_pc1.txt", after_pc)
    step("reinicio_pc1", ok=True)

    stop("worker")
    while_down = b"cambio con observador detenido\n"
    write("pc1", "Mientras_observador_caido.txt", while_down)
    wait_file("hub", "Mientras_observador_caido.txt", while_down)
    start_worker()
    step("reinicio_observador",
         recuperacion_s=round(wait_versions("Mientras_observador_caido.txt", [("MODIFIED", sha(while_down))]), 2))

    # Corte de red de pc1 (pausar el dispositivo hub) y recuperación.
    ids = {n: request(n, "GET", "/rest/system/status")["myID"] for n in NODES}
    request("pc1", "POST", "/rest/system/pause", params={"device": ids["hub"]})
    cut = b"editado durante corte de red\n"
    write("pc1", "Corte_red.txt", cut)
    time.sleep(3)
    assert not (HUB_SHARE / "Corte_red.txt").exists(), "no debe llegar con la red cortada"
    request("pc1", "POST", "/rest/system/resume", params={"device": ids["hub"]})
    step("corte_y_recuperacion_red", convergencia_s=round(wait_file("hub", "Corte_red.txt", cut), 2))

    # Edición concurrente offline: ambos contenidos deben sobrevivir.
    base = b"BASE\n"
    write("pc1", "Concurrente.txt", base)
    wait_file("pc2", "Concurrente.txt", base)
    wait_versions("Concurrente.txt", [("MODIFIED", sha(base))])
    stop("hub")
    left, right = b"CAMBIO-PC1\n", b"CAMBIO-PC2\n"
    write("pc1", "Concurrente.txt", left)
    write("pc2", "Concurrente.txt", right)
    time.sleep(2)
    start("hub")

    def both_on_hub():
        contents = {p.read_bytes() for p in HUB_SHARE.glob("Concurrente*") if p.is_file()}
        return left in contents and right in contents

    wait_until("ambas versiones concurrentes en hub", both_on_hub, timeout=120)
    conflict_rows = lambda: rows(
        "SELECT d.logical_path, v.sha256, v.analysis_status FROM document_versions v "
        "JOIN document_records d ON d.id = v.document_id WHERE v.change_kind = 'CONFLICT'")
    wait_until("conflicto registrado", conflict_rows, timeout=60)
    shas = {r[1] for r in conflict_rows()} | {versions("Concurrente.txt")[-1][1]}
    step("conflicto_offline", ambas_preservadas={sha(left), sha(right)} <= shas,
         estado=sorted({r[2] for r in conflict_rows()}),
         content_store=all(stored(d) for d in (sha(left), sha(right))))

    # Colisión de mayúsculas en el hub Linux: no debe detener el observador.
    stop("hub")
    write("pc1", "Radio.txt", b"pc1")
    write("pc2", "radio.txt", b"pc2")
    time.sleep(2)
    start("hub")
    wait_file("hub", "Radio.txt", b"pc1")
    wait_file("hub", "radio.txt", b"pc2")
    probe = b"despues de la colision\n"
    write("pc1", "Tras_colision.txt", probe)
    wait_file("hub", "Tras_colision.txt", probe)
    step("colision_mayusculas", observador_sigue=wait_versions("Tras_colision.txt", [("MODIFIED", sha(probe))]) >= 0,
         cuarentena=not rows("SELECT 1 FROM document_records WHERE lower(logical_path) = 'radio.txt'"),
         worker_vivo=PROCS["worker"].poll() is None)

    extended_scenarios()

    for path in sorted(p for p in HUB_SHARE.rglob("*") if p.is_file() and ".stversions" not in p.parts
                       and ".stfolder" not in p.parts):
        rel = path.relative_to(HUB_SHARE).as_posix()
        EVIDENCE["files"][rel] = sha(path.read_bytes())
    EVIDENCE["worker_usage"] = proc_usage(PROCS["worker"].pid)
    EVIDENCE["hub_syncthing_usage"] = proc_usage(PROCS["hub"].pid)
    EVIDENCE["versions_bytes"] = sum(p.stat().st_size for p in VERSIONS.rglob("*") if p.is_file())
    EVIDENCE["worker_log_tail"] = (ROOT / "worker.log").read_text(errors="replace").splitlines()[-15:]


def attribution(path: str) -> dict:
    found = rows(
        "SELECT v.metadata_json FROM document_versions v JOIN document_records d ON d.id = v.document_id "
        "WHERE d.logical_path = ? ORDER BY v.observed_at DESC LIMIT 1", path)
    return (json.loads(found[0][0]) if found else {}).get("attribution", {})


def observer_status() -> dict:
    meta = rows("SELECT metadata_json FROM sync_shares WHERE code = 'LAB_SYNC'")[0][0]
    return json.loads(meta or "{}").get("observer", {})


def deleted_count() -> int:
    return rows("SELECT count(*) FROM document_versions WHERE change_kind = 'DELETED'")[0][0]


def extended_scenarios():
    # Atribución técnica de dispositivo (Syncthing modifiedBy): sin persona.
    from_pc2 = b"escrito en pc2\n"
    write("pc2", "Desde_pc2.txt", from_pc2)
    wait_versions("Desde_pc2.txt", [("MODIFIED", sha(from_pc2))])
    first = attribution("Inventario_LAB.xlsx")
    second = attribution("Desde_pc2.txt")
    step("atribucion_dispositivo", pc1=first, pc2=second)
    assert first.get("peer_code") == "LAB-PC1" and first.get("verified") is True, first
    assert second.get("peer_code") == "LAB-PC2" and second.get("verified") is True, second
    assert first.get("person") is None and first.get("scope") == "DEVICE"

    # Cambios rápidos: el registro converge al contenido final sin versiones inconsistentes.
    final = None
    for i in range(20):
        final = f"version rapida {i}\n".encode() * (i + 1)
        write("pc1", "Rapido.txt", final)
    wait_file("hub", "Rapido.txt", final)
    wait_until("última versión de Rapido.txt registrada",
               lambda: versions("Rapido.txt") and versions("Rapido.txt")[-1][1] == sha(final), timeout=60)
    consistent = all(
        (VERSIONS / "sha256" / d[:2] / d).stat().st_size == size
        for d, size in rows("SELECT v.sha256, v.size_bytes FROM document_versions v JOIN document_records r "
                            "ON r.id = v.document_id WHERE r.logical_path = 'Rapido.txt'")
    )
    step("cambios_rapidos", escrituras=20, versiones_registradas=len(versions("Rapido.txt")),
         tamano_coherente_con_objeto=consistent)
    assert consistent

    # Archivo que genera error (nombre no portable a Windows): se aísla y queda como evidencia.
    write("pc1", "Reporte:final.txt", b"dos puntos no valen en Windows")
    wait_file("hub", "Reporte:final.txt", b"dos puntos no valen en Windows")
    probe = b"el observador sigue\n"
    write("pc1", "Tras_error.txt", probe)
    wait_versions("Tras_error.txt", [("MODIFIED", sha(probe))])
    issues = observer_status().get("issues", [])
    step("archivo_con_error", incidencias=[i for i in issues if "Reporte" in i["path"]],
         worker_vivo=PROCS["worker"].poll() is None)
    assert any(i["code"] == "NAME_NOT_PORTABLE" and "Reporte" in i["path"] for i in issues), issues

    # Caída de la raíz del hub (punto de montaje vacío) y recuperación.
    before = deleted_count()
    pc1_files = sorted(p.name for p in folder_path("pc1").iterdir() if p.is_file())
    offline = HUB_SHARE.with_name("LAB_SYNC.desmontado")
    HUB_SHARE.rename(offline)
    HUB_SHARE.mkdir()
    wait_until("observador UNAVAILABLE",
               lambda: observer_status().get("code") == "SYNCTHING_MARKER_MISSING", timeout=30)
    during = b"creado durante la caida del hub\n"
    write("pc1", "Durante_caida.txt", during)
    time.sleep(8)
    step("caida_raiz", estado=observer_status().get("state"), codigo=observer_status().get("code"),
         borrados_nuevos=deleted_count() - before, worker_vivo=PROCS["worker"].poll() is None)
    assert deleted_count() == before, "falsos borrados durante la caída"
    HUB_SHARE.rmdir()
    offline.rename(HUB_SHARE)
    request("hub", "PATCH", f"/rest/config/folders/{FOLDER}", payload={"paused": True})
    request("hub", "PATCH", f"/rest/config/folders/{FOLDER}", payload={"paused": False})
    wait_file("hub", "Durante_caida.txt", during)
    wait_versions("Durante_caida.txt", [("MODIFIED", sha(during))])
    wait_until("observador AVAILABLE", lambda: observer_status().get("state") == "AVAILABLE", timeout=30)
    pc1_after = sorted(p.name for p in folder_path("pc1").iterdir() if p.is_file())
    step("recuperacion_raiz", borrados_nuevos=deleted_count() - before,
         pc1_sin_perdidas=set(pc1_files) <= set(pc1_after))
    assert deleted_count() == before and set(pc1_files) <= set(pc1_after)

    # Consistencia final DB <-> versions/ con SHA recalculado.
    verify = subprocess.run([sys.executable, "-m", "app.workers.verify_history", "--deep"],
                            env=so_env(), cwd=REPO, capture_output=True, text=True)
    step("verify_history_deep", salida=verify.stdout.strip().splitlines()[0], exit=verify.returncode)
    assert verify.returncode == 0, verify.stdout


def main() -> int:
    if not BIN:
        print("SYNCTHING_BIN no definido y syncthing no está en PATH", file=sys.stderr)
        return 2
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)
    EVIDENCE["syncthing"] = subprocess.run([BIN, "--version"], capture_output=True, text=True).stdout.strip()
    EVIDENCE["python"] = sys.version.split()[0]
    for node in NODES:
        generate(node)
    HUB_SHARE.mkdir(parents=True)
    try:
        for node in NODES:
            start(node)
        ids = configure()
        prepare_server_oficina(ids)
        start_worker()
        run()
        EVIDENCE["result"] = "HUB_WORKER_LAB_OK"
        print("HUB_WORKER_LAB_OK", flush=True)
        return 0
    except Exception as exc:
        EVIDENCE["result"] = f"FAIL: {exc}"
        if (ROOT / "worker.log").exists():
            print((ROOT / "worker.log").read_text(errors="replace")[-4000:], file=sys.stderr)
        raise
    finally:
        for name in list(PROCS):
            stop(name)
        (ROOT / "evidence.json").write_text(json.dumps(EVIDENCE, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
