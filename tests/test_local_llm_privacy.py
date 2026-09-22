import pytest

from app.services.local_llm import is_private_llm_url, chat_json
from app.services.syncthing_adapter import SyncthingClient


def test_local_llm_endpoint_is_fail_closed():
    assert is_private_llm_url("http://127.0.0.1:8081/v1")
    assert is_private_llm_url("http://192.168.48.10:8081/v1")
    assert not is_private_llm_url("https://api.example.com/v1")
    with pytest.raises(ValueError):
        chat_json(
            base_url="https://api.example.com/v1", model="x", system="x", user="x",
            json_schema={"type": "object"}, timeout_seconds=0.01,
        )


def test_syncthing_adapter_rejects_public_control_plane():
    with pytest.raises(ValueError):
        SyncthingClient("https://sync.example.com", "secret")
    assert SyncthingClient("http://127.0.0.1:8384", "secret").recommended_topology()["topology"] == "STAR"
