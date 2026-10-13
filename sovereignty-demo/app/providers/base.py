from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

import httpx

from app.network_meter import NetworkMeter

PROMPT_TEMPLATE = """You are a helpful assistant. Use the document below to answer the request.

<document>
{document}
</document>

Request: {prompt}"""

# The orchestrator enforces the overall per-panel timeout; this only bounds connecting.
HTTP_TIMEOUT = httpx.Timeout(None, connect=5.0)


def build_prompt(prompt: str, document: str) -> str:
    """FR-03: user prompt plus document text injected as context."""
    return PROMPT_TEMPLATE.format(prompt=prompt, document=document)


class ProviderError(RuntimeError):
    """A failure with a message safe to show on screen (never contains keys or document text)."""


class ProviderAdapter(Protocol):
    name: str
    model: str
    host: str
    is_external: bool

    def stream(self, prompt: str, document: str, meter: NetworkMeter) -> AsyncIterator[str]: ...
