#!/usr/bin/env python3
"""Diagnóstico mDNS de sólo lectura: ¿por qué una PC no resuelve ``server-oficina.local``?

Captura UDP 5353 en UNA interfaz de la Latitude con un socket AF_PACKET (sin
tcpdump ni dependencias), en los dos sentidos, y separa las capas del fallo:

1. anuncio: la Latitude responde por esa interfaz con registros A/AAAA de su
   nombre, y sólo con direcciones de esa interfaz (nunca las de Docker);
2. multicast en la LAN: llegan a la Latitude paquetes mDNS de otros equipos;
3. la PC (``--peer``) consulta por el nombre y su consulta llega a la Latitude;
4. la Latitude contesta a esa consulta (multicast o unicast, y a qué destino).

Lo que pasa después (si la respuesta llega a la PC y si Windows la acepta) sólo
se ve con una captura en la PC. No envía ningún paquete ni cambia nada. Con
``--pcap`` guarda únicamente las tramas UDP 5353 para abrirlas en Wireshark.

Uso (root):
  python3 diagnostico_mdns.py --interfaz wlo1 --peer 192.168.48.219 [--segundos 180] [--pcap F] [--todo]
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import subprocess
import sys
import time

ETH_P_ALL = 0x0003
PACKET_OUTGOING = 4
MDNS_PORT = 5353
MULTICAST = {"224.0.0.251", "ff02::fb"}
TIPOS = {1: "A", 5: "CNAME", 12: "PTR", 13: "HINFO", 16: "TXT", 28: "AAAA", 33: "SRV", 47: "NSEC", 255: "ANY"}

LECTURA = {
    "CONFLICTO_NOMBRE": "otro equipo de la LAN responde con el mismo nombre: conflicto mDNS",
    "LATITUDE_ANUNCIA_DIRECCION_AJENA": "la Latitude anuncia por esta interfaz direcciones que no son suyas en ella "
                                        "(p. ej. Docker): defecto del lado Latitude",
    "SIN_MULTICAST_ENTRANTE": "no llegó ningún paquete mDNS de la LAN: el punto de acceso o la red no entregan "
                              "multicast a la Latitude (o nadie consultó durante la captura)",
    "CONSULTAS_DE_LA_PC_NO_LLEGAN": "llega multicast de otros equipos pero nada de la PC: la PC no envía mDNS "
                                    "o el punto de acceso aísla a ese cliente; confirmar con la captura de la PC",
    "PC_NO_PREGUNTA_POR_EL_NOMBRE": "llega mDNS de la PC, pero nunca por este nombre: el resolvedor de la PC "
                                    "no consulta mDNS para él",
    "LATITUDE_NO_RESPONDE": "la consulta de la PC llegó y la Latitude no respondió: defecto del lado Latitude",
    "LATITUDE_RESPONDE": "la consulta de la PC llegó y la respuesta salió por esta interfaz; si la PC no "
                         "resuelve, la respuesta no le llega o la descarta: ver la captura de la PC",
    "SIN_CONSULTAS": "nadie preguntó por el nombre durante la captura",
}


class Malformado(ValueError):
    pass


def _nombre(data: bytes, pos: int) -> tuple[str, int]:
    """Nombre DNS (con compresión); devuelve el nombre y la posición tras él."""
    etiquetas: list[str] = []
    fin = None
    saltos = 0
    while True:
        if pos >= len(data):
            raise Malformado("nombre truncado")
        largo = data[pos]
        if largo & 0xC0 == 0xC0:
            if pos + 1 >= len(data):
                raise Malformado("puntero truncado")
            if fin is None:
                fin = pos + 2
            pos = ((largo & 0x3F) << 8) | data[pos + 1]
            saltos += 1
            if saltos > 32:
                raise Malformado("bucle de compresión")
            continue
        if largo & 0xC0:
            raise Malformado("etiqueta inválida")
        pos += 1
        if largo == 0:
            return ".".join(etiquetas), (fin if fin is not None else pos)
        if pos + largo > len(data):
            raise Malformado("etiqueta truncada")
        etiquetas.append(data[pos:pos + largo].decode("utf-8", "replace"))
        pos += largo


def parse_dns(data: bytes) -> dict:
    if len(data) < 12:
        raise Malformado("cabecera DNS truncada")
    _id, flags, qd, an, ns, ar = struct.unpack("!6H", data[:12])
    pos = 12
    preguntas = []
    for _ in range(qd):
        nombre, pos = _nombre(data, pos)
        if pos + 4 > len(data):
            raise Malformado("pregunta truncada")
        qtype, qclass = struct.unpack("!2H", data[pos:pos + 4])
        pos += 4
        preguntas.append({"nombre": nombre, "tipo": TIPOS.get(qtype, str(qtype)), "qu": bool(qclass & 0x8000)})
    registros = []
    for seccion, total in (("an", an), ("ns", ns), ("ar", ar)):
        for _ in range(total):
            nombre, pos = _nombre(data, pos)
            if pos + 10 > len(data):
                raise Malformado("registro truncado")
            rtype, _rclass, ttl, rdlen = struct.unpack("!HHIH", data[pos:pos + 10])
            pos += 10
            rdata = data[pos:pos + rdlen]
            if len(rdata) != rdlen:
                raise Malformado("rdata truncado")
            pos += rdlen
            valor = None
            if rtype == 1 and rdlen == 4:
                valor = socket.inet_ntop(socket.AF_INET, rdata)
            elif rtype == 28 and rdlen == 16:
                valor = socket.inet_ntop(socket.AF_INET6, rdata)
            registros.append({"seccion": seccion, "nombre": nombre, "tipo": TIPOS.get(rtype, str(rtype)),
                              "ttl": ttl, "valor": valor})
    return {"respuesta": bool(flags & 0x8000), "preguntas": preguntas, "registros": registros}


def parse_frame(frame: bytes) -> dict | None:
    """Trama Ethernet → paquete mDNS decodificado, o None si no es UDP 5353."""
    if len(frame) < 14:
        return None
    ethertype, off = struct.unpack("!H", frame[12:14])[0], 14
    if ethertype == 0x8100 and len(frame) >= 18:
        ethertype, off = struct.unpack("!H", frame[16:18])[0], 18
    if ethertype == 0x0800:
        if len(frame) < off + 20 or frame[off] >> 4 != 4:
            return None
        ihl = (frame[off] & 0x0F) * 4
        fragmento = struct.unpack("!H", frame[off + 6:off + 8])[0] & 0x1FFF
        if ihl < 20 or frame[off + 9] != 17 or fragmento:
            return None
        familia = "IPv4"
        origen = socket.inet_ntop(socket.AF_INET, frame[off + 12:off + 16])
        destino = socket.inet_ntop(socket.AF_INET, frame[off + 16:off + 20])
        l4 = off + ihl
    elif ethertype == 0x86DD:
        if len(frame) < off + 40 or frame[off + 6] != 17:  # mDNS no usa cabeceras de extensión
            return None
        familia = "IPv6"
        origen = socket.inet_ntop(socket.AF_INET6, frame[off + 8:off + 24])
        destino = socket.inet_ntop(socket.AF_INET6, frame[off + 24:off + 40])
        l4 = off + 40
    else:
        return None
    if len(frame) < l4 + 8:
        return None
    sport, dport, largo = struct.unpack("!3H", frame[l4:l4 + 6])
    if MDNS_PORT not in (sport, dport):
        return None
    paquete = {"familia": familia, "origen": origen, "destino": destino,
               "puerto_origen": sport, "puerto_destino": dport,
               "mac_destino": frame[0:6].hex(":"), "mac_origen": frame[6:12].hex(":")}
    try:
        paquete.update(parse_dns(frame[l4 + 8:l4 + max(largo, 8)]))
    except Malformado as exc:
        paquete["malformado"] = str(exc)
    return paquete


def _es(nombre: str, buscado: str) -> bool:
    return nombre.lower().rstrip(".") == buscado


class Resumen:
    """Acumula lo observado en la interfaz; ``registrar`` dice si el paquete es relevante."""

    def __init__(self, nombre: str, peer: str | None, propias: set[str] | None, peer_mac: str | None = None):
        self.nombre = nombre.lower().rstrip(".")
        self.peer = peer
        # La PC también consulta por IPv6 link-local: se la reconoce por su MAC (tabla de vecinos).
        self.peer_mac = peer_mac.lower() if peer_mac else None
        self.propias = propias  # None: no se pudieron leer las direcciones de la interfaz
        self.entrantes = self.salientes = self.ecos = self.malformados = 0
        self.origenes: set[str] = set()
        self.origenes_peer: set[str] = set()
        self.consultas_peer = 0
        self.consultas_peer_nombre = 0
        self.consultas_peer_qu = 0
        self.consultas_nombre_de: set[str] = set()
        self.respuestas_nombre = 0
        self.respuestas_tras_peer = 0
        self.destinos_respuesta: set[str] = set()
        self.anunciadas: set[str] = set()
        self.ajenas: set[str] = set()
        self.otros_responden: set[str] = set()

    def _desde_peer(self, p: dict) -> bool:
        return bool(self.peer) and (p["origen"] == self.peer or (self.peer_mac is not None
                                                                 and p.get("mac_origen") == self.peer_mac))

    def _hacia_peer(self, p: dict) -> bool:
        return bool(self.peer) and (p["destino"] == self.peer or (self.peer_mac is not None
                                                                  and p.get("mac_destino") == self.peer_mac))

    def registrar(self, p: dict, saliente: bool) -> bool:
        if "malformado" in p:
            self.malformados += 1
            return self._desde_peer(p) or self._hacia_peer(p)
        pregunta_nombre = [q for q in p["preguntas"] if _es(q["nombre"], self.nombre)]
        direcciones = [r["valor"] for r in p["registros"]
                       if _es(r["nombre"], self.nombre) and r["tipo"] in ("A", "AAAA") and r["valor"]]
        if saliente:
            self.salientes += 1
            if p["respuesta"] and direcciones:
                self.respuestas_nombre += 1
                self.anunciadas.update(direcciones)
                if self.propias is not None:
                    self.ajenas.update(d for d in direcciones if d not in self.propias)
                self.destinos_respuesta.add(f'{p["destino"]}:{p["puerto_destino"]}')
                if self.consultas_peer_nombre and (p["destino"] in MULTICAST or self._hacia_peer(p)):
                    self.respuestas_tras_peer += 1
        elif self.propias is not None and p["origen"] in self.propias:
            self.ecos += 1  # el punto de acceso reenvía el multicast propio
            return False
        else:
            self.entrantes += 1
            self.origenes.add(p["origen"])
            if self._desde_peer(p):
                self.origenes_peer.add(p["origen"])
            if pregunta_nombre and not p["respuesta"]:
                self.consultas_nombre_de.add(p["origen"])
            if p["respuesta"] and direcciones:
                self.otros_responden.add(p["origen"])
            if self._desde_peer(p) and not p["respuesta"]:
                self.consultas_peer += 1
                if pregunta_nombre:
                    self.consultas_peer_nombre += 1
                    self.consultas_peer_qu += any(q["qu"] for q in pregunta_nombre)
        return bool(pregunta_nombre or direcciones or self._desde_peer(p) or self._hacia_peer(p))

    def diagnostico(self) -> str:
        if self.otros_responden:
            return "CONFLICTO_NOMBRE"
        if self.ajenas:
            return "LATITUDE_ANUNCIA_DIRECCION_AJENA"
        if self.peer is None:
            return "LATITUDE_RESPONDE" if self.consultas_nombre_de and self.respuestas_nombre else "SIN_CONSULTAS"
        if self.consultas_peer_nombre:
            return "LATITUDE_RESPONDE" if self.respuestas_tras_peer else "LATITUDE_NO_RESPONDE"
        if self.consultas_peer:
            return "PC_NO_PREGUNTA_POR_EL_NOMBRE"
        otros = self.origenes - {self.peer} - self.origenes_peer
        return "CONSULTAS_DE_LA_PC_NO_LLEGAN" if otros else "SIN_MULTICAST_ENTRANTE"

    def como_dict(self) -> dict:
        return {
            "nombre": self.nombre, "peer": self.peer, "peer_mac": self.peer_mac,
            "direcciones_peer": sorted(self.origenes_peer),
            "direcciones_interfaz": sorted(self.propias) if self.propias is not None else None,
            "entrantes": self.entrantes, "salientes": self.salientes, "ecos": self.ecos,
            "malformados": self.malformados, "equipos_emisores": sorted(self.origenes),
            "consultas_nombre_de": sorted(self.consultas_nombre_de),
            "consultas_peer": self.consultas_peer, "consultas_peer_nombre": self.consultas_peer_nombre,
            "consultas_peer_qu": self.consultas_peer_qu,
            "respuestas_nombre": self.respuestas_nombre, "respuestas_tras_peer": self.respuestas_tras_peer,
            "destinos_respuesta": sorted(self.destinos_respuesta), "direcciones_anunciadas": sorted(self.anunciadas),
            "direcciones_ajenas": sorted(self.ajenas), "otros_responden_nombre": sorted(self.otros_responden),
            "diagnostico": self.diagnostico(),
        }


def linea(ts: float, p: dict, saliente: bool) -> str:
    hora = time.strftime("%H:%M:%S", time.localtime(ts)) + f".{int(ts * 1000) % 1000:03d}"
    cabeza = (f'{hora} {"SALE " if saliente else "ENTRA"} {p["familia"]} '
              f'{p["origen"]}:{p["puerto_origen"]} -> {p["destino"]}:{p["puerto_destino"]}')
    if "malformado" in p:
        return f"{cabeza} malformado ({p['malformado']})"
    if p["respuesta"]:
        partes = [f'{r["nombre"]}/{r["tipo"]}' + (f'={r["valor"]}' if r["valor"] else "")
                  for r in p["registros"] if r["seccion"] == "an"]
        detalle = "respuesta " + ", ".join(partes[:6]) + (f" (+{len(partes) - 6})" if len(partes) > 6 else "")
    else:
        partes = [f'{q["nombre"]}/{q["tipo"]}' + ("[QU]" if q["qu"] else "") for q in p["preguntas"]]
        detalle = "consulta " + ", ".join(partes[:6]) + (f" (+{len(partes) - 6})" if len(partes) > 6 else "")
    return f"{cabeza} {detalle}"


def direcciones_propias(interfaz: str) -> set[str] | None:
    try:
        salida = subprocess.run(["ip", "-j", "addr", "show", "dev", interfaz], capture_output=True, text=True,
                                check=True, timeout=10).stdout
        return {a["local"] for i in json.loads(salida) for a in i.get("addr_info", []) if a.get("local")}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def mac_vecino(interfaz: str, ip: str | None) -> str | None:
    """MAC de la PC según la tabla de vecinos (existe si la PC ya habló con la Latitude)."""
    if not ip:
        return None
    try:
        salida = subprocess.run(["ip", "-j", "neigh", "show", ip, "dev", interfaz], capture_output=True, text=True,
                                check=True, timeout=10).stdout
        return next((v["lladdr"] for v in json.loads(salida) if v.get("lladdr")), None)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def abrir_pcap(ruta: str):
    fh = open(ruta, "wb")
    fh.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))  # LINKTYPE_ETHERNET
    return fh


def escribir_pcap(fh, ts: float, frame: bytes) -> None:
    fh.write(struct.pack("<IIII", int(ts), int((ts % 1) * 1_000_000), len(frame), len(frame)))
    fh.write(frame)


def capturar(sock, hasta: float, resumen: Resumen, salida=sys.stdout, pcap=None, todo=False,
             reloj=time.time) -> None:
    while (restante := hasta - reloj()) > 0:
        sock.settimeout(min(1.0, restante))
        try:
            frame, direccion = sock.recvfrom(65535)
        except (socket.timeout, TimeoutError):
            continue
        paquete = parse_frame(frame)
        if paquete is None:
            continue
        saliente = len(direccion) > 2 and direccion[2] == PACKET_OUTGOING
        ts = reloj()
        if pcap is not None:
            escribir_pcap(pcap, ts, frame)
        if resumen.registrar(paquete, saliente) or todo:
            print(linea(ts, paquete, saliente), file=salida, flush=True)


def imprimir_resumen(r: Resumen, interfaz: str, segundos: float, salida=sys.stdout) -> None:
    d = r.como_dict()
    ajenas = ", ".join(d["direcciones_ajenas"]) or "ninguna"
    if d["direcciones_interfaz"] is None:
        ajenas = "sin comprobar (no se leyeron las direcciones de la interfaz)"
    print(f"\n== Resumen mDNS en {interfaz} ({segundos:.0f} s) ==", file=salida)
    print(f'paquetes UDP 5353: entrantes={d["entrantes"]} salientes={d["salientes"]} '
          f'ecos={d["ecos"]} malformados={d["malformados"]}', file=salida)
    print(f'[capa 1] respuestas de la Latitude con A/AAAA de {r.nombre}: {d["respuestas_nombre"]}; '
          f'direcciones anunciadas: {", ".join(d["direcciones_anunciadas"]) or "ninguna"}; '
          f'ajenas a {interfaz}: {ajenas}', file=salida)
    print(f'[capa 2] equipos que emitieron mDNS hacia la Latitude: {len(d["equipos_emisores"])} '
          f'{d["equipos_emisores"][:12]}', file=salida)
    if r.peer:
        print(f'[capa 3] consultas de {r.peer} (MAC {r.peer_mac or "desconocida"}, '
              f'desde {", ".join(d["direcciones_peer"]) or "ninguna dirección"}): {d["consultas_peer"]} (por {r.nombre}: '
              f'{d["consultas_peer_nombre"]}, con QU: {d["consultas_peer_qu"]})', file=salida)
        print(f'[capa 4] respuestas de la Latitude tras esas consultas: {d["respuestas_tras_peer"]} '
              f'(destinos: {", ".join(d["destinos_respuesta"]) or "ninguno"})', file=salida)
    else:
        print(f'[capa 3] consultas por {r.nombre} de: {d["consultas_nombre_de"] or "nadie"}', file=salida)
    print(f'DIAGNOSTICO: {d["diagnostico"]} — {LECTURA[d["diagnostico"]]}', file=salida)
    print("MDNS_DIAG " + json.dumps(d, ensure_ascii=False, sort_keys=True), file=salida, flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--interfaz", required=True, help="interfaz de la LAN a observar (p. ej. wlo1)")
    ap.add_argument("--peer", help="IPv4/IPv6 de la PC que intenta resolver el nombre")
    ap.add_argument("--nombre", default=f"{socket.gethostname().split('.')[0]}.local")
    ap.add_argument("--segundos", type=float, default=180.0)
    ap.add_argument("--pcap", help="guardar las tramas UDP 5353 (sólo esas) en este archivo")
    ap.add_argument("--todo", action="store_true", help="mostrar todo el mDNS, no sólo el nombre y la PC")
    args = ap.parse_args(argv)
    if not os.path.isdir(f"/sys/class/net/{args.interfaz}"):
        print(f"no existe la interfaz {args.interfaz}", file=sys.stderr)
        return 2
    try:
        sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
        sock.bind((args.interfaz, ETH_P_ALL))
    except PermissionError:
        print("se necesita root (sudo) para capturar", file=sys.stderr)
        return 1
    resumen = Resumen(args.nombre, args.peer, direcciones_propias(args.interfaz),
                      mac_vecino(args.interfaz, args.peer))
    pcap = abrir_pcap(args.pcap) if args.pcap else None
    if pcap is not None and os.environ.get("SUDO_UID"):
        os.chown(args.pcap, int(os.environ["SUDO_UID"]), int(os.environ.get("SUDO_GID", "-1")))
    print(f"capturando UDP 5353 en {args.interfaz} durante {args.segundos:.0f} s "
          f"(nombre={resumen.nombre} peer={args.peer or '-'} mac={resumen.peer_mac or '-'}); sólo escucha",
          flush=True)
    inicio = time.time()
    try:
        capturar(sock, inicio + args.segundos, resumen, pcap=pcap, todo=args.todo)
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        if pcap is not None:
            pcap.close()
    imprimir_resumen(resumen, args.interfaz, time.time() - inicio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
