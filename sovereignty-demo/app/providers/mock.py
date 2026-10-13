"""Deterministic fake streamers (FR-30).

Mocks send real httpx requests through the panel's NetworkMeter, served by an in-process
httpx.MockTransport. Byte counts and payload capture therefore use the same code path as live
providers, with no network access.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator

import httpx

from app.network_meter import NetworkMeter
from app.providers.base import build_prompt

LOCAL_ANSWER = (
    "Summary (mock, local model): The memo describes a proposed acquisition and asks the board "
    "to approve the next stage of due diligence. It names a target company, a deal value and an "
    "internal reference. Main risks: valuation, integration cost and confidentiality before "
    "announcement. Recommended next step: limit circulation and confirm advisers."
)

HOSTED_ANSWER = (
    "Summary (mock, hosted model): This board memo proposes moving an acquisition into due "
    "diligence. It identifies the target, the proposed price and an internal tracking ID. Key "
    "risks are price, integration and leaks before the deal is public. Suggested action: approve "
    "diligence with a tight distribution list."
)


def _chunks(text: str) -> list[str]:
    return re.findall(r"\S+\s*", text)


class MockAdapter:
    def __init__(
        self,
        *,
        name: str,
        model: str,
        base_url: str,
        is_external: bool,
        answer: str,
        token_delay_s: float,
    ) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url
        self.host = httpx.URL(base_url).host
        self.is_external = is_external
        self.answer = answer
        self.token_delay_s = token_delay_s

    def _transport(self) -> httpx.MockTransport:
        async def body() -> AsyncIterator[bytes]:
            for chunk in _chunks(self.answer):
                await asyncio.sleep(self.token_delay_s)
                yield chunk.encode()

        return httpx.MockTransport(lambda request: httpx.Response(200, content=body()))

    async def stream(self, prompt: str, document: str, meter: NetworkMeter) -> AsyncIterator[str]:
        payload = {"model": self.model, "stream": True, "messages": [{"role": "user", "content": build_prompt(prompt, document)}]}
        async with meter.client(transport=self._transport(), base_url=self.base_url) as client:
            async with client.stream("POST", "/v1/chat", json=payload) as response:
                async for chunk in response.aiter_text():
                    yield chunk


def mock_local(token_delay_s: float) -> MockAdapter:
    return MockAdapter(
        name="Local open-weight model",
        model="mock-local-3b",
        base_url="http://localhost:11434",
        is_external=False,
        answer=LOCAL_ANSWER,
        token_delay_s=token_delay_s,
    )


def mock_hosted(token_delay_s: float) -> MockAdapter:
    return MockAdapter(
        name="Hosted API",
        model="mock-hosted-large",
        base_url="https://api.hosted-provider.example",
        is_external=True,
        answer=HOSTED_ANSWER,
        token_delay_s=token_delay_s,
    )
