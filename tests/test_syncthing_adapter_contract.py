import json

import pytest

import app.services.syncthing_adapter as mod
from app.services.syncthing_adapter import SyncthingClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_client_rejects_public_or_missing_credentials():
    with pytest.raises(ValueError):
        SyncthingClient("https://sync.example.com", "x")
    with pytest.raises(ValueError):
        SyncthingClient("http://127.0.0.1:8384", "")


def test_completion_uses_supported_query_contract(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        return FakeResponse({"completion": 100, "needItems": 0})

    monkeypatch.setattr(mod, "urlopen", fake_urlopen)
    client = SyncthingClient("http://127.0.0.1:8384", "secret")
    result = client.completion(folder="material", device="AAAA")
    assert result["completion"] == 100
    assert "folder=material" in seen["url"]
    assert "device=AAAA" in seen["url"]


def test_upsert_folder_posts_json(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["method"] = req.get_method()
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data.decode())
        return FakeResponse({"ok": True})

    monkeypatch.setattr(mod, "urlopen", fake_urlopen)
    client = SyncthingClient("http://127.0.0.1:8384", "secret")
    client.upsert_folder({"id": "rrhh", "path": "/srv/files/RRHH")
    assert seen["method"] == "POST"
    assert seen["url"].endswith("/rest/config/folders")
    assert seen["body"]["id"] == "rrhh"
