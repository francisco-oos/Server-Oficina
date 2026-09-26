from __future__ import annotations

"""Cliente restringido para la API REST de Syncthing.

Server Oficina usa Syncthing como motor de transporte de archivos, no como
fuente de verdad. El cliente sólo acepta loopback o redes privadas y nunca
expone la API key en respuestas de aplicación.
"""

import ipaddress
import json
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


def _private_base(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.hostname == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


class SyncthingClient:
    def __init__(self, base_url: str, api_key: str, *, timeout: float = 10.0):
        if not _private_base(base_url):
            raise ValueError("Syncthing API debe vivir en loopback o red privada")
        if not api_key:
            raise ValueError("Syncthing API key requerida")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, *, params: dict | None = None, payload=None):
        query = ("?" + urlencode(params)) if params else ""
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request(
            self.base_url + path + query,
            data=data,
            method=method.upper(),
            headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
        )
        with urlopen(req, timeout=self.timeout) as response:
            body = response.read()
            if not body:
                return None
            return json.loads(body.decode("utf-8"))

    def _get(self, path: str, **params):
        return self._request("GET", path, params=params or None)

    def system_status(self) -> dict:
        return self._get("/rest/system/status")

    def system_connections(self) -> dict:
        return self._get("/rest/system/connections")

    def config_status(self) -> dict:
        return self._get("/rest/config/restart-required")

    def options(self) -> dict:
        return self._get("/rest/config/options")

    def patch_options(self, patch: dict):
        return self._request("PATCH", "/rest/config/options", payload=patch)

    def devices(self) -> list[dict]:
        return self._get("/rest/config/devices")

    def upsert_device(self, payload: dict):
        return self._request("POST", "/rest/config/devices", payload=payload)

    def folders(self) -> list[dict]:
        return self._get("/rest/config/folders")

    def upsert_folder(self, payload: dict):
        return self._request("POST", "/rest/config/folders", payload=payload)

    def folder_status(self, folder: str) -> dict:
        return self._get("/rest/db/status", folder=folder)

    def completion(self, *, folder: str | None = None, device: str | None = None) -> dict:
        params = {}
        if folder:
            params["folder"] = folder
        if device:
            params["device"] = device
        return self._get("/rest/db/completion", **params)

    def file_info(self, *, folder: str, relative_path: str) -> dict:
        return self._get("/rest/db/file", folder=folder, file=relative_path)

    def events(self, *, since: int = 0, limit: int = 100, timeout: int = 5) -> list[dict]:
        return self._get("/rest/events", since=since, limit=limit, timeout=timeout)

    @staticmethod
    def recommended_topology() -> dict:
        return {
            "topology": "STAR",
            "hub": "server-oficina",
            "internet_discovery": False,
            "relays": False,
            "nat_traversal": False,
            "versioning": "staggered_plus_server_oficina_document_versions",
            "delete_policy": "server_oficina_archive_before_purge",
        }
