"""Hosted provider via the OpenAI Chat Completions REST API (FR-11). Also works with
OpenAI-compatible endpoints by changing OPENAI_BASE_URL."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

import httpx

from app.network_meter import NetworkMeter
from app.providers.base import HTTP_TIMEOUT, ProviderError, build_prompt

STATUS_MESSAGES = {
    401: "Hosted provider rejected the API key (HTTP 401)",
    403: "Hosted provider refused access (HTTP 403)",
    404: "Hosted model not found (HTTP 404)",
    429: "Hosted provider rate limit or quota reached (HTTP 429)",
}


class OpenAIAdapter:
    name = "Hosted API"
    is_external = True

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key_env: str = "OPENAI_API_KEY",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.host = httpx.URL(self.base_url).host
        self._api_key_env = api_key_env
        self._transport = transport

    async def stream(self, prompt: str, document: str, meter: NetworkMeter) -> AsyncIterator[str]:
        api_key = os.environ.get(self._api_key_env)
        if not api_key:
            raise ProviderError(f"{self._api_key_env} is not set")
        payload = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "user", "content": build_prompt(prompt, document)}],
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        async with meter.client(transport=self._transport, base_url=self.base_url, timeout=HTTP_TIMEOUT) as client:
            try:
                async with client.stream("POST", "/chat/completions", json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        raise ProviderError(STATUS_MESSAGES.get(response.status_code, f"Hosted provider returned HTTP {response.status_code}"))
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        event = json.loads(data)
                        if "error" in event:
                            raise ProviderError("Hosted provider reported an error mid-stream")
                        for choice in event.get("choices", []):
                            if text := choice.get("delta", {}).get("content"):
                                yield text
            except httpx.ConnectError:
                raise ProviderError(f"Cannot reach {self.host}") from None
