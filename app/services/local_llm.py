from __future__ import annotations

"""Adaptador mínimo a un LLM local compatible con OpenAI/llama.cpp.

Privacidad por defecto: sólo loopback o redes privadas RFC1918/ULA. Una URL
pública se rechaza antes de hacer I/O. El LLM interpreta; nunca escribe directo
en tablas de dominio.
"""

import ipaddress
import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def is_private_llm_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname
    if host in {"localhost"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def chat_json(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    json_schema: dict,
    timeout_seconds: float = 45.0,
) -> dict:
    if not is_private_llm_url(base_url):
        raise ValueError("El endpoint LLM debe ser loopback o una IP privada")
    endpoint = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_schema", "schema": json_schema},
    }
    request = Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout_seconds) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    return json.loads(content)
