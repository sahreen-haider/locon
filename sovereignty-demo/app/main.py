"""FastAPI app: REST routes and the /ws event stream."""

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import STATIC_DIR, ConfigUpdate, Mode, Settings, api_key_present
from app.documents import DocumentNotFound, list_documents, load_document
from app.events import EventBus
from app.orchestrator import Orchestrator
from app.providers import ProviderUnavailable, build_adapters

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


class RunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    document_id: str
    mode: Mode | None = None


async def _ollama_reachable(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            return (await client.get(f"{url}/api/version")).status_code == 200
    except httpx.HTTPError:
        return False


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    bus = EventBus()
    orchestrator = Orchestrator(bus)
    app = FastAPI(title="Sovereignty Demo Dashboard")
    app.state.settings, app.state.bus, app.state.orchestrator = settings, bus, orchestrator

    @app.get("/api/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "mode": settings.mode,
            "ollama_reachable": await _ollama_reachable(settings.ollama_url),
            "api_keys": {p: api_key_present(p) for p in ("openai", "anthropic", "gemini")},
        }

    @app.get("/api/config")
    async def get_config() -> dict:
        return settings.public()

    @app.post("/api/config")
    async def update_config(update: ConfigUpdate) -> dict:
        for key, value in update.model_dump(exclude_none=True).items():
            setattr(settings, key, value)
        bus.publish({"type": "config", **settings.public()})
        return settings.public()

    @app.get("/api/documents")
    async def documents() -> list[dict]:
        return list_documents()

    @app.post("/api/run")
    async def run(req: RunRequest) -> dict:
        try:
            document = load_document(req.document_id)
        except DocumentNotFound:
            raise HTTPException(404, f"Unknown document: {req.document_id}") from None
        run_settings = settings.model_copy(update={"mode": req.mode}) if req.mode else settings
        try:
            adapters = build_adapters(run_settings)
        except ProviderUnavailable as exc:
            raise HTTPException(409, str(exc)) from None
        run_id = orchestrator.start(req.prompt, document, adapters, settings.panel_timeout_s, settings.canaries)
        return {"run_id": run_id}

    @app.post("/api/reset")
    async def reset() -> dict:
        orchestrator.reset()
        return {"status": "reset"}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = bus.subscribe()

        async def send() -> None:
            await websocket.send_json({"type": "config", **settings.public()})
            while True:
                await websocket.send_json(await queue.get())

        async def receive() -> None:
            while True:
                await websocket.receive_text()

        tasks = [asyncio.create_task(send()), asyncio.create_task(receive())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except WebSocketDisconnect:
            pass
        finally:
            for task in tasks:
                task.cancel()
            bus.unsubscribe(queue)

    if (STATIC_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app


app = create_app()
