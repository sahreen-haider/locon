"""Fans one run out to both panels concurrently. A slow or failing panel never blocks the other."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

from app.events import EventBus
from app.network_meter import NetworkMeter
from app.providers.base import ProviderAdapter

log = logging.getLogger(__name__)


@dataclass
class PanelResult:
    panel: str
    state: str  # done | error
    text: str = ""
    detail: str = ""
    ttft_ms: int | None = None
    total_ms: int = 0
    external_bytes_out: int = 0
    destinations: list[dict] = field(default_factory=list)


class Orchestrator:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._task: asyncio.Task | None = None
        self.run_id: str | None = None

    def start(
        self, prompt: str, document: str, adapters: dict[str, ProviderAdapter], timeout_s: float, canaries: list[str] = ()
    ) -> str:
        """Start a run in the background, cancelling any run still in progress."""
        self.cancel()
        run_id = uuid.uuid4().hex[:8]
        self.run_id = run_id
        self._task = asyncio.create_task(self.run(run_id, prompt, document, adapters, timeout_s, canaries))
        return run_id

    def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    def reset(self) -> None:
        self.cancel()
        self.run_id = None
        self.bus.publish({"type": "reset"})

    async def run(
        self,
        run_id: str,
        prompt: str,
        document: str,
        adapters: dict[str, ProviderAdapter],
        timeout_s: float,
        canaries: list[str] = (),
    ) -> dict[str, PanelResult]:
        log.info("run %s started", run_id)
        results = await asyncio.gather(
            *(
                self._run_panel(run_id, panel, adapter, prompt, document, timeout_s, list(canaries))
                for panel, adapter in adapters.items()
            )
        )
        log.info("run %s finished: %s", run_id, {r.panel: r.state for r in results})
        return {r.panel: r for r in results}

    async def _run_panel(
        self,
        run_id: str,
        panel: str,
        adapter: ProviderAdapter,
        prompt: str,
        document: str,
        timeout_s: float,
        canaries: list[str],
    ) -> PanelResult:
        def emit(event: dict) -> None:
            self.bus.publish({**event, "run_id": run_id})

        meter = NetworkMeter(panel, emit, canaries)
        emit({
            "type": "status", "panel": panel, "state": "running",
            "detail": "", "label": adapter.name, "model": adapter.model, "host": adapter.host,
        })
        result = PanelResult(panel=panel, state="done")
        parts: list[str] = []
        start = time.perf_counter()
        try:
            async with asyncio.timeout(timeout_s):
                async for chunk in adapter.stream(prompt, document, meter):
                    if result.ttft_ms is None:
                        result.ttft_ms = round((time.perf_counter() - start) * 1000)
                    parts.append(chunk)
                    emit({"type": "token", "panel": panel, "text": chunk})
        except TimeoutError:
            result.state, result.detail = "error", f"No response within {timeout_s:g} seconds"
        except Exception as exc:  # noqa: BLE001  one panel failing must not break the other
            log.warning("panel %s failed: %s", panel, type(exc).__name__)
            result.state, result.detail = "error", str(exc) or type(exc).__name__

        result.text = "".join(parts)
        result.total_ms = round((time.perf_counter() - start) * 1000)
        result.external_bytes_out = meter.external_bytes_out
        result.destinations = [vars(d) for d in meter.destinations.values()]
        emit({"type": "metrics", "panel": panel, "ttft_ms": result.ttft_ms, "total_ms": result.total_ms})
        emit({"type": "status", "panel": panel, "state": result.state, "detail": result.detail})
        return result
