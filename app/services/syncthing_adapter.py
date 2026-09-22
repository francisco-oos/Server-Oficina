from __future__ import annotations

"""Cliente restringido para el Syncthing local de la Latitude."""

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
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, path: str, **params):
        query = ("?" + urlencode(params)) if params else ""
        req = Request(self.base_url + path + query, headers={"X-API-Key": self.api_key})
        with urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def system_status(self) -> dict:
        return self._get("/rest/system/status")

    def folder_status(self, folder: str) -> dict:
        return self._get("/rest/db/status", folder=folder)

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
            "versioning": "staggered_or_external_on_hub",
            "delete_policy": "server_oficina_archive_before_purge",
        }
