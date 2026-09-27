"""scripts/diagnostico_mdns.py: captura mDNS de sólo lectura que separa las capas del fallo ``.local``.

Origen (gate físico 1, 2026-09-27): la PC Windows llega a la API por IP en la
Wi-Fi, pero ``server-oficina.local`` no resuelve. Avahi registra la IP de
``wlo1``; hace falta saber si la consulta de la PC llega, si la Latitude
responde y con qué dirección, sin instalar tcpdump en la Latitude.
"""

import importlib.util
import io
import json
import socket
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("diagnostico_mdns", ROOT / "scripts" / "diagnostico_mdns.py")
dm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dm)

NOMBRE = "server-oficina.local"
LATITUDE, PC, OTRO = "192.168.48.109", "192.168.48.219", "192.168.48.40"
LATITUDE_V6, PC_V6 = "fe80::d23c:1fff:fe4b:148c", "fe80::1234:56ff:fe78:9abc"
MAC_LATITUDE, MAC_PC, MAC_OTRO = "d0:3c:1f:4b:14:8c", "aa:bb:cc:dd:ee:21", "aa:bb:cc:dd:ee:40"
PROPIAS = {LATITUDE, LATITUDE_V6}


def _nombre(nombre: str) -> bytes:
    return b"".join(bytes([len(e)]) + e.encode() for e in nombre.split(".")) + b"\0"


def consulta(nombre=NOMBRE, qtype=1, qu=False) -> bytes:
    return struct.pack("!6H", 0, 0, 1, 0, 0, 0) + _nombre(nombre) + struct.pack("!2H", qtype, 1 | (0x8000 if qu else 0))


def respuesta(*direcciones, nombre=NOMBRE) -> bytes:
    cuerpo = b""
    for d in direcciones:
        v6 = ":" in d
        rdata = socket.inet_pton(socket.AF_INET6 if v6 else socket.AF_INET, d)
        cuerpo += _nombre(nombre) + struct.pack("!HHIH", 28 if v6 else 1, 0x8001, 120, len(rdata)) + rdata
    return struct.pack("!6H", 0, 0x8400, 0, len(direcciones), 0, 0) + cuerpo


def trama(origen, destino, dns, smac=MAC_PC, dmac="01:00:5e:00:00:fb", sport=5353, dport=5353, proto=17,
          frag=0, vlan=False) -> bytes:
    udp = struct.pack("!4H", sport, dport, 8 + len(dns), 0) + dns
    if ":" in origen:
        ip = struct.pack("!IHBB", 0x60000000, len(udp), proto, 255)
        ip += socket.inet_pton(socket.AF_INET6, origen) + socket.inet_pton(socket.AF_INET6, destino)
        tipo = 0x86DD
    else:
        ip = struct.pack("!BBHHHBBH", 0x45, 0, 20 + len(udp), 0, frag, 255, proto, 0)
        ip += socket.inet_aton(origen) + socket.inet_aton(destino)
        tipo = 0x0800
    eth = bytes.fromhex(dmac.replace(":", "")) + bytes.fromhex(smac.replace(":", ""))
    eth += (struct.pack("!HH", 0x8100, 1) if vlan else b"") + struct.pack("!H", tipo)
    return eth + ip + udp


def _resumen(peer=PC, peer_mac=MAC_PC):
    return dm.Resumen(NOMBRE, peer, set(PROPIAS), peer_mac)


def test_parse_ipv4_query_with_qu_bit_and_macs():
    p = dm.parse_frame(trama(PC, "224.0.0.251", consulta(qu=True)))
    assert (p["familia"], p["origen"], p["destino"], p["mac_origen"]) == ("IPv4", PC, "224.0.0.251", MAC_PC)
    assert p["respuesta"] is False
    assert p["preguntas"] == [{"nombre": NOMBRE, "tipo": "A", "qu": True}]


def test_parse_ipv6_response_with_compressed_name():
    pregunta = _nombre(NOMBRE) + struct.pack("!2H", 28, 1)
    dns = (struct.pack("!6H", 0, 0x8400, 1, 1, 0, 0) + pregunta
           + b"\xc0\x0c" + struct.pack("!HHIH", 28, 0x8001, 120, 16) + socket.inet_pton(socket.AF_INET6, LATITUDE_V6))
    p = dm.parse_frame(trama(LATITUDE_V6, "ff02::fb", dns, smac=MAC_LATITUDE, dmac="33:33:00:00:00:fb"))
    assert p["familia"] == "IPv6" and p["respuesta"] is True
    assert p["registros"] == [{"seccion": "an", "nombre": NOMBRE, "tipo": "AAAA", "ttl": 120, "valor": LATITUDE_V6}]


def test_parse_vlan_tagged_frame():
    assert dm.parse_frame(trama(PC, "224.0.0.251", consulta(), vlan=True))["origen"] == PC


@pytest.mark.parametrize("kwargs", [{"sport": 40000, "dport": 53}, {"proto": 6}, {"frag": 5}])
def test_non_mdns_frames_are_ignored(kwargs):
    assert dm.parse_frame(trama(PC, "224.0.0.251", consulta(), **kwargs)) is None


def test_malformed_dns_is_reported_not_raised():
    truncada = dm.parse_frame(trama(PC, "224.0.0.251", consulta()[:15]))
    bucle = dm.parse_frame(trama(PC, "224.0.0.251", struct.pack("!6H", 0, 0, 1, 0, 0, 0) + b"\xc0\x0c"))
    assert "malformado" in truncada and "malformado" in bucle


def _registrar(r, *eventos):
    for frame, saliente in eventos:
        r.registrar(dm.parse_frame(frame), saliente)
    return r


def test_latitude_answers_the_pc_query():
    r = _registrar(_resumen(),
                   (trama(PC, "224.0.0.251", consulta()), False),
                   (trama(LATITUDE, "224.0.0.251", respuesta(LATITUDE), smac=MAC_LATITUDE), True))
    assert r.diagnostico() == "LATITUDE_RESPONDE"
    d = r.como_dict()
    assert d["respuestas_tras_peer"] == 1 and d["direcciones_ajenas"] == [] and d["destinos_respuesta"] == ["224.0.0.251:5353"]


def test_unicast_answer_to_the_pc_counts():
    r = _registrar(_resumen(),
                   (trama(PC, "224.0.0.251", consulta(qu=True)), False),
                   (trama(LATITUDE, PC, respuesta(LATITUDE), smac=MAC_LATITUDE, dmac=MAC_PC), True))
    assert r.diagnostico() == "LATITUDE_RESPONDE" and r.consultas_peer_qu == 1


def test_pc_querying_only_over_ipv6_is_recognised_by_mac():
    r = _registrar(_resumen(),
                   (trama(PC_V6, "ff02::fb", consulta(qtype=28)), False),
                   (trama(LATITUDE_V6, "ff02::fb", respuesta(LATITUDE_V6), smac=MAC_LATITUDE), True))
    assert r.consultas_peer_nombre == 1 and r.diagnostico() == "LATITUDE_RESPONDE"
    assert r.como_dict()["direcciones_peer"] == [PC_V6]


def test_query_arrives_but_latitude_is_silent():
    r = _registrar(_resumen(), (trama(PC, "224.0.0.251", consulta()), False))
    assert r.diagnostico() == "LATITUDE_NO_RESPONDE"


def test_answer_before_the_pc_query_does_not_count_as_reply():
    r = _registrar(_resumen(),
                   (trama(LATITUDE, "224.0.0.251", respuesta(LATITUDE), smac=MAC_LATITUDE), True),
                   (trama(PC, "224.0.0.251", consulta()), False))
    assert r.diagnostico() == "LATITUDE_NO_RESPONDE"


def test_lan_multicast_arrives_but_nothing_from_the_pc():
    r = _registrar(_resumen(), (trama(OTRO, "224.0.0.251", consulta("impresora.local"), smac=MAC_OTRO), False))
    assert r.diagnostico() == "CONSULTAS_DE_LA_PC_NO_LLEGAN"


def test_no_multicast_at_all_and_own_echoes_are_not_lan_traffic():
    r = _registrar(_resumen(), (trama(LATITUDE, "224.0.0.251", respuesta(LATITUDE), smac=MAC_LATITUDE), False))
    assert r.ecos == 1 and r.origenes == set()
    assert r.diagnostico() == "SIN_MULTICAST_ENTRANTE"


def test_pc_sends_mdns_but_never_for_the_name():
    r = _registrar(_resumen(), (trama(PC, "224.0.0.251", consulta("_googlecast._tcp.local", qtype=12)), False))
    assert r.diagnostico() == "PC_NO_PREGUNTA_POR_EL_NOMBRE"


def test_docker_address_announced_on_the_lan_is_a_latitude_defect():
    r = _registrar(_resumen(),
                   (trama(PC, "224.0.0.251", consulta()), False),
                   (trama(LATITUDE, "224.0.0.251", respuesta("172.18.0.1", LATITUDE), smac=MAC_LATITUDE), True))
    assert r.diagnostico() == "LATITUDE_ANUNCIA_DIRECCION_AJENA"
    assert r.como_dict()["direcciones_ajenas"] == ["172.18.0.1"]


def test_another_host_answering_the_name_is_a_conflict():
    r = _registrar(_resumen(), (trama(OTRO, "224.0.0.251", respuesta(OTRO), smac=MAC_OTRO), False))
    assert r.diagnostico() == "CONFLICTO_NOMBRE"


class FakeSocket:
    def __init__(self, eventos):
        self.eventos = list(eventos)

    def settimeout(self, _):
        pass

    def recvfrom(self, _):
        if not self.eventos:
            raise socket.timeout()
        return self.eventos.pop(0)


def test_capture_prints_relevant_packets_and_writes_only_mdns_to_pcap(tmp_path):
    reloj = iter(range(1000, 2000)).__next__
    otro_trafico = trama(PC, LATITUDE, b"x" * 20, sport=51000, dport=8080)
    sock = FakeSocket([
        (otro_trafico, ("wlo1", 0x0800, 0, 1, b"")),
        (trama(PC, "224.0.0.251", consulta()), ("wlo1", 0x0800, 2, 1, b"")),
        (trama(LATITUDE, "224.0.0.251", respuesta(LATITUDE), smac=MAC_LATITUDE), ("wlo1", 0x0800, 4, 1, b"")),
        (trama(OTRO, "224.0.0.251", consulta("impresora.local"), smac=MAC_OTRO), ("wlo1", 0x0800, 2, 1, b"")),
    ])
    r, salida = _resumen(), io.StringIO()
    with dm.abrir_pcap(str(tmp_path / "c.pcap")) as pcap:
        dm.capturar(sock, 1010, r, salida=salida, pcap=pcap, reloj=reloj)
    lineas = salida.getvalue().splitlines()
    assert len(lineas) == 2  # la consulta ajena no se imprime sin --todo
    assert "ENTRA IPv4 192.168.48.219:5353 -> 224.0.0.251:5353 consulta server-oficina.local/A" in lineas[0]
    assert "SALE  IPv4 192.168.48.109:5353 -> 224.0.0.251:5353 respuesta server-oficina.local/A=192.168.48.109" in lineas[1]
    datos = (tmp_path / "c.pcap").read_bytes()
    assert struct.unpack("<I", datos[:4])[0] == 0xA1B2C3D4
    registros, pos = 0, 24
    while pos < len(datos):
        largo = struct.unpack("<IIII", datos[pos:pos + 16])[2]
        assert dm.parse_frame(datos[pos + 16:pos + 16 + largo]) is not None
        pos, registros = pos + 16 + largo, registros + 1
    assert registros == 3  # sólo UDP 5353: el HTTP no se guarda


def test_summary_is_machine_readable():
    r = _registrar(_resumen(), (trama(PC, "224.0.0.251", consulta()), False))
    salida = io.StringIO()
    dm.imprimir_resumen(r, "wlo1", 180, salida=salida)
    texto = salida.getvalue()
    assert "DIAGNOSTICO: LATITUDE_NO_RESPONDE" in texto
    datos = json.loads(texto.split("MDNS_DIAG ", 1)[1])
    assert datos["diagnostico"] == "LATITUDE_NO_RESPONDE" and datos["peer_mac"] == MAC_PC


def test_every_diagnosis_has_an_explanation():
    codigos = {"CONFLICTO_NOMBRE", "LATITUDE_ANUNCIA_DIRECCION_AJENA", "SIN_MULTICAST_ENTRANTE",
               "CONSULTAS_DE_LA_PC_NO_LLEGAN", "PC_NO_PREGUNTA_POR_EL_NOMBRE", "LATITUDE_NO_RESPONDE",
               "LATITUDE_RESPONDE", "SIN_CONSULTAS"}
    assert set(dm.LECTURA) == codigos


def test_the_tool_never_transmits():
    codigo = (ROOT / "scripts" / "diagnostico_mdns.py").read_text(encoding="utf-8")
    assert ".send(" not in codigo and ".sendto(" not in codigo and "sendmsg" not in codigo


def test_unknown_interface_is_rejected_before_opening_a_socket(capsys):
    assert dm.main(["--interfaz", "no-existe-0"]) == 2
    assert "no existe la interfaz" in capsys.readouterr().err
