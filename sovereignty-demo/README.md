# Sovereignty Demo Dashboard

Split-screen demo for the Sovereign AI section of the KW-Sprint executive workshop: a local
open-weight model next to a hosted API, with live network instrumentation showing where the
document goes. Illustrative demo with fictional data. Not a verdict on any vendor.

Spec: `../sovereignty-demo-dashboard.md`. Contributor rules: `CLAUDE.md`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env   # optional, defaults to mock mode
```

## Run

```bash
DEMO_MODE=mock .venv/bin/uvicorn app.main:app --reload    # rehearsal, no network
.venv/bin/uvicorn app.main:app --env-file .env           # live: set DEMO_MODE=live and OPENAI_API_KEY in .env
.venv/bin/pytest -q
```

## Status

- Phase 0 and 1 done: scaffold, health, provider adapter interface, MockAdapter, orchestrator, `/ws` event stream.
- Phase 2 done: NetworkMeter counts bytes per destination via an httpx transport, captures external payloads, tags canary strings. Mocks use the same path through httpx.MockTransport.
- Phase 3 code done: OllamaAdapter (default `qwen2.5:0.5b`) and OpenAIAdapter (default `gpt-4.1-mini`), tested against fake transports. Real-count verification pending Ollama install and an API key.
