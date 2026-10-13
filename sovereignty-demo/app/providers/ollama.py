"""Local open-weight model via the Ollama HTTP API (FR-10)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.network_meter import NetworkMeter
from app.providers.base import HTTP_TIMEOUT, ProviderError, build_prompt


class OllamaAdapter:
    name = "Local open-weight model"
    is_external = False

    def __init__(self, base_url: str, model: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.host = httpx.URL(self.base_url).host
        self._transport = transport

    async def stream(self, prompt: str, document: str, meter: NetworkMeter) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "user", "content": build_prompt(prompt, document)}],
            "options": {"temperature": 0, "seed": 7},
            "keep_alive": "30m",
        }
        async with meter.client(transport=self._transport, base_url=self.base_url, timeout=HTTP_TIMEOUT) as client:
            try:
                async with client.stream("POST", "/api/chat", json=payload) as response:
                    if response.status_code == 404:
                        raise ProviderError(f"Model {self.model} is not available. Run: ollama pull {self.model}")
                    if response.status_code != 200:
                        raise ProviderError(f"Ollama returned HTTP {response.status_code}")
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        event = json.loads(line)
                        if "error" in event:
                            raise ProviderError(f"Ollama error: {event['error']}")
                        if text := event.get("message", {}).get("content"):
                            yield text
                        if event.get("done"):
                            return
            except httpx.ConnectError:
                raise ProviderError(f"Ollama is not running at {self.base_url}") from None
