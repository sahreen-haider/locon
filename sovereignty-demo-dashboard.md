# Sovereignty Demo Dashboard

Ideation, FRD and Claude Code build guide.
Owner: Sahreen Haider. Status: Draft v1. Purpose: closing demo for the Sovereign AI section of the Kuwait executive workshop (KW-Sprint).

---

## 1. Context

- Audience: executives and non-technical decision makers.
- Section pillars: AI Today, Governance, AI Sovereignty.
- Constraint: the demo must NOT become a product pitch. No Vatoz or VesselX content.
- Slot: 60 to 90 seconds inside a 35 minute talk. It replaces other time, it does not extend the talk.
- Thesis the demo must prove: "Where your AI runs decides who controls your data."

## 2. Ideation Summary

Options considered (see section 2.1), and the chosen concept.

### 2.1 Options considered

| # | Idea | Verdict |
|---|------|---------|
| 1 | Air-gap test (local model, Wi-Fi off) | Folded into chosen concept |
| 2 | Network traffic view of a hosted AI call | Folded into chosen concept |
| 3 | Same question, different guardrails | Parked, Governance demo for later |
| 4 | Provenance and access control with RAG | Parked, too many moving parts |
| 5 | Kill switch on provider dependency | Backup as animated slide |
| 6 | Arabic and local context comparison | Strong secondary idea, stretch goal |
| 7 | Prompt injection via hidden document text | Included as optional mode |
| 8 | Voice clone | Rejected, belongs to the cybersecurity section |
| 9 | Live audience poll | Backup, zero tech risk |
| 10 | Live sovereignty scorecard | Backup, zero tech risk |

### 2.2 Chosen concept

A split screen dashboard. Left: an open-weight model running locally. Right: a proprietary hosted API. One shared prompt and one shared fictional secret document are sent to both. Live network instrumentation shows that the local side sends nothing off the machine, while the hosted side sends the full document to a third party, with the sensitive strings highlighted in the outbound payload.

### 2.3 Honest framing (must appear in the talk and in the UI footer)

- Hosted enterprise tiers may offer no-training and data residency terms. The demo shows the default data path, not a verdict on any vendor.
- Local models are usually less capable. Sovereignty is a trade-off between capability and control.
- Self-hosted does not mean secure. Access control and governance still apply.

## 3. Goals and Non-Goals

### Goals
- G1: Make data location visible in under 90 seconds to a non-technical audience.
- G2: Run reliably on one laptop, with a fully offline mock mode for rehearsal.
- G3: Produce a recordable, deterministic run as the default delivery format.
- G4: Be reusable for future workshops (swap provider, swap model, swap document).

### Non-Goals
- Not a benchmark of model quality or speed.
- Not a security product, scanner, or production tool.
- No real customer or company data, ever.
- No claim that any named vendor is unsafe.

## 4. Users and Scenarios

- Primary user: presenter (Sahreen) operating the dashboard on stage or recording it.
- Secondary user: rehearsal operator using mock mode.
- Audience: watches the screen only.

Scenarios:
1. Live-or-recorded run: load fake memo, send to both panels, point at the traffic and payload.
2. Offline test: toggle "Disconnect network", hosted panel fails, local panel keeps answering.
3. Injection mode: load the poisoned document, show how each model reacts.
4. Rehearsal: run entirely in mock mode with no Ollama and no API key.

## 5. Functional Requirements (FRD)

Priority: P0 must have, P1 should have, P2 nice to have.

### 5.1 Input and document handling
- FR-01 (P0): Single prompt input shared by both panels, one Send button dispatches to both in parallel.
- FR-02 (P0): Document selector with bundled fictional documents (memo, large memo, poisoned proposal). Plain text and .docx supported, parsed to text server side.
- FR-03 (P0): Prompt template: user prompt plus document text injected as context.
- FR-04 (P1): Upload custom document (size limit 2 MB).
- FR-05 (P1): "Large document" preset (about 300 KB, generated filler plus canary strings) so network spikes are visible.

### 5.2 Model panels
- FR-10 (P0): Left panel: local model via Ollama HTTP API, streaming tokens.
- FR-11 (P0): Right panel: hosted provider via adapter interface, streaming tokens.
- FR-12 (P0): Provider adapter interface so OpenAI, Anthropic, Gemini can be swapped by config.
- FR-13 (P0): Each panel shows label, model name, host being called, status (idle, running, done, error), time to first token, total time.
- FR-14 (P1): Per-panel error display that does not break the other panel.

### 5.3 Network instrumentation
- FR-20 (P0): Instrumented HTTP client wrapper counts bytes sent and received per destination host for each panel.
- FR-21 (P0): Per-panel "External bytes sent" counter. Local panel expected 0 (localhost excluded from external count). Hosted panel shows actual request size.
- FR-22 (P0): Destination list per panel (host, port, bytes out, bytes in).
- FR-23 (P0): Payload inspector: shows the outbound request body as sent by the app (pre-TLS), with configured canary strings highlighted. Local panel shows "No external payload".
- FR-24 (P0): Canary string config (list of strings to highlight, default from the bundled memo).
- FR-25 (P1): System network graph using psutil interface counters, sampled every 500 ms, rolling 60 s window, cumulative total shown beside it.
- FR-26 (P1): Per-process connection view (psutil) listing remote endpoints for the backend process, to show the OS-level view is consistent with the app-level view.
- FR-27 (P2): Optional Wireshark or system monitor overlay is out of scope for the app, documented in the runbook.

### 5.4 Modes and controls
- FR-30 (P0): Mock mode: both providers replaced by deterministic fake streamers and fake network counters. Selectable by env var and UI toggle.
- FR-31 (P0): "Disconnect network" simulation toggle: blocks outbound calls to non-local hosts at the app layer so the hosted panel fails visibly while local continues. UI must label this as a simulation. Real Wi-Fi off is the manual alternative.
- FR-32 (P1): Injection mode: loads the poisoned document and a user prompt asking for a risk summary, then shows a "Did the model follow the hidden instruction?" indicator (simple keyword check on output, shown as a hint only).
- FR-33 (P1): Reset button clears panels, counters and payload views.
- FR-34 (P1): Record helper: one-click "Demo run" button that executes the scripted scenario with fixed timings for consistent screen recording.
- FR-35 (P2): Export run log (JSON) with timings, byte counts, destinations.

### 5.5 UI and presentation
- FR-40 (P0): 16:9 layout optimised for projector, large type, high contrast, readable at the back of a room.
- FR-41 (P0): Colour semantics: local panel green accent, hosted panel amber accent, canary highlights red. Never rely on colour alone (add icons and labels).
- FR-42 (P0): Footer line always visible: "Illustrative demo with fictional data. Not a verdict on any vendor."
- FR-43 (P1): Presenter mode: hides debug controls, shows only the two panels and the key counters.
- FR-44 (P2): Theme tokens so the design can follow the Citadel Quantum Consortium design language used in the deck.

## 6. Non-Functional Requirements

- NFR-01: Cold start to ready under 10 seconds (excluding model pull).
- NFR-02: Works fully offline in mock mode and local-only mode.
- NFR-03: No secrets in the repo. API keys via environment variables only, `.env` git-ignored.
- NFR-04: Use a throwaway provider account and fictional data only.
- NFR-05: First token on local model under 5 seconds on the target laptop with the chosen model (verify, adjust model size).
- NFR-06: UI must not freeze if one provider hangs. 30 second timeout per panel.
- NFR-07: Logging must not write document contents to disk by default.
- NFR-08: Runs on macOS and Linux, Windows best effort.

## 7. Architecture

```
Browser (single page)
  |  WebSocket /ws  (events: token, status, net, payload, metrics)
  |  REST /api/*    (documents, config, run)
FastAPI backend
  |-- Orchestrator: fans out one run to both providers concurrently
  |-- ProviderAdapter (interface)
  |     |-- OllamaAdapter     -> http://localhost:11434
  |     |-- HostedAdapter(s)  -> OpenAI | Anthropic | Gemini
  |     |-- MockAdapter       -> deterministic fake stream
  |-- NetworkMeter: wraps httpx with event hooks, counts bytes per host,
  |                 captures outbound body, tags canary strings
  |-- SystemSampler: psutil net_io_counters + connections, 500 ms loop
  |-- DocumentService: loads and parses bundled/uploaded docs
```

Key design decision: all provider calls go through one instrumented httpx client per panel so byte counts and payload capture are consistent. The UI states that the payload view is "as sent by the app, before encryption" because TLS hides it on the wire.

### 7.1 Event schema (WebSocket, JSON)

```json
{"type":"status","panel":"local|hosted","state":"idle|running|done|error","detail":"..."}
{"type":"token","panel":"local|hosted","text":"..."}
{"type":"net","panel":"local|hosted","host":"api.example.com","bytes_out":12345,"bytes_in":6789,"external":true}
{"type":"payload","panel":"hosted","body":"...","canary_hits":[{"text":"Project Falcon","start":120,"end":134}]}
{"type":"sys","ts":1730000000,"rx_bps":1200,"tx_bps":98000,"tx_total":1048576}
{"type":"metrics","panel":"local|hosted","ttft_ms":820,"total_ms":6400}
```

### 7.2 REST endpoints

- `GET  /api/config` current mode, models, providers, canary list
- `POST /api/config` update mode, provider, model, offline-simulation flag
- `GET  /api/documents` list bundled documents
- `POST /api/documents` upload custom document (P1)
- `POST /api/run` body: `{prompt, document_id, mode}` starts a run, returns `run_id`
- `POST /api/reset` clears state
- `GET  /api/health` backend, Ollama reachability, provider key presence (boolean only)

### 7.3 Provider adapter interface

```python
class ProviderAdapter(Protocol):
    name: str
    is_external: bool
    async def stream(self, prompt: str, document: str, meter: NetworkMeter) -> AsyncIterator[str]: ...
```

Each adapter must send its HTTP traffic through the provided `meter` so counts and payloads are captured.

## 8. Tech Stack

- Backend: Python 3.11+, FastAPI, uvicorn, httpx (async, streaming), psutil, python-docx, pydantic, websockets.
- Frontend: single `index.html` with vanilla JS and a small chart lib (uPlot or Chart.js), no build step.
- Local model: Ollama. Candidate models to test: a 3B to 8B open-weight model (Llama, Qwen, Mistral or Gemma class). Choose by measured first-token time on the demo laptop.
- Hosted: one of OpenAI, Anthropic, Gemini via official REST, selected by env var.
- Tests: pytest, pytest-asyncio.

## 9. Project Structure

```
sovereignty-demo/
  README.md
  CLAUDE.md
  .env.example
  pyproject.toml
  app/
    main.py              # FastAPI app, routes, websocket
    config.py            # settings, env, canary list
    orchestrator.py      # fan-out run logic
    network_meter.py     # httpx hooks, byte counts, payload capture
    system_sampler.py    # psutil sampler
    documents.py         # load/parse docs
    providers/
      base.py
      ollama.py
      openai_like.py
      anthropic.py
      gemini.py
      mock.py
  static/
    index.html
    app.js
    styles.css
  data/
    memo_small.txt
    memo_large.txt       # generated by script
    proposal_poisoned.txt
  scripts/
    make_large_doc.py
    demo_run.py          # scripted scenario for recording
  tests/
    test_network_meter.py
    test_orchestrator_mock.py
    test_canary_tagging.py
  docs/
    runbook.md
    demo_script.md
```

## 10. Fictional Data (bundled)

Never use real data. Canary strings:
- Project codename: "Project Falcon"
- Target: "Zentra Ltd"
- Figure: "USD 212M"
- Fake internal ID: "BM-7731-KX"

`memo_small.txt`: a one-page fake board memo about an acquisition, containing all four canary strings.
`proposal_poisoned.txt`: fake supplier proposal with visible red flags (no certification, unspecified hosting, data reuse clause) plus an injected instruction block telling an assistant to call the supplier low risk and not mention the note. The injection is harmless: it only changes the summary wording.

## 11. UI Specification

- Header: title, mode badge (LIVE or MOCK), network badge (ONLINE, OFFLINE-SIM).
- Top bar: document dropdown, prompt box, Send, Reset, Demo Run.
- Two equal columns:
  - Column header: icon, label, model name, host.
  - Streaming answer area.
  - Counter row: External bytes sent, destinations count, TTFT, total time.
  - Destination table.
  - Payload inspector (collapsed by default in presenter mode, auto-expands on run).
- Bottom strip: system network graph (60 s window) and cumulative TX total.
- Footer: disclaimer text (FR-42).
- Key visual moment: hosted payload inspector with canary strings lit in red next to the local panel's "No external payload" state.

## 12. Demo Script (target 75 seconds)

1. (0:00) "Same document, same question, two ways to run AI." Show split screen.
2. (0:10) Press Send. Both stream answers.
3. (0:25) Point left: "Zero bytes left this machine." Point right: counters rising.
4. (0:35) Open hosted payload: "This is what the provider received. Our codename, our target, our figure."
5. (0:50) Toggle Disconnect network: hosted fails, local keeps working.
6. (1:05) Close line: "Control has a cost in capability, and a benefit in custody. Sovereignty is choosing that trade on purpose."

Fallback: play the recorded clip with the same narration.

## 13. Test Plan and Acceptance Criteria

Acceptance (all P0 must pass):
- AC-01: In mock mode with no network, a run completes and both panels stream.
- AC-02: Local panel reports 0 external bytes in a live run.
- AC-03: Hosted panel reports non-zero external bytes and the payload view shows at least one highlighted canary string.
- AC-04: With the offline simulation on, the hosted panel shows a clear error within 3 seconds and the local panel still completes.
- AC-05: A hung provider does not block the other panel (30 s timeout).
- AC-06: No API key or document text appears in logs by default.
- AC-07: Disclaimer footer visible in every mode.

Unit tests: byte counting per host, canary tagging offsets, orchestrator concurrency with mock providers, config validation.
Manual: rehearsal on the actual presentation laptop and projector, with and without venue Wi-Fi.

## 14. Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Local model too slow on laptop | Smaller or quantised model, pre-warm, tested threshold NFR-05 |
| Live API or venue Wi-Fi fails | Recorded clip is the default, mock mode as backup |
| Network graph barely moves (prompt is a few KB) | Large document preset, cumulative counters, payload inspector as hero visual |
| Payload not visible on the wire due to TLS | Label clearly "as sent by the app, before encryption" |
| Audience reads it as an attack on a vendor | Footer disclaimer, honest framing in the talk |
| Hosted model refuses or behaves differently | Pre-test, keep the best honest recorded run, state that results vary |
| Injection mode inconsistent | Keep it optional, treat a failed attempt as a talking point |

## 15. Build Phases for Claude Code

Phase 0: Scaffold repo, `pyproject.toml`, `.env.example`, `CLAUDE.md`, health endpoint.
Phase 1: Provider adapter interface, MockAdapter, orchestrator, WebSocket events. Done when AC-01 passes.
Phase 2: NetworkMeter with httpx hooks, canary tagging, tests. Done when AC-02 and AC-03 logic pass against mocks.
Phase 3: OllamaAdapter and one hosted adapter. Verify real counts.
Phase 4: Frontend: split layout, counters, payload inspector, disclaimer.
Phase 5: SystemSampler graph, offline simulation toggle, reset.
Phase 6: Demo Run script, large document generator, presenter mode.
Phase 7: Injection mode, polish, runbook, rehearsal.

Stretch: Arabic and local-context comparison mode (idea 6), run log export, deck design tokens.

## 16. CLAUDE.md (copy into repo root)

```markdown
# Sovereignty Demo Dashboard

## What this is
Split-screen demo: local open-weight model vs hosted API, with live network
instrumentation. For an executive workshop. Illustrative, fictional data only.

## Rules
- Never use real company data or real secrets. Only the bundled fictional documents.
- API keys come from environment variables. Never commit .env.
- Do not log document contents or API keys.
- All provider HTTP traffic must go through NetworkMeter. No direct httpx/requests calls in adapters.
- Payload view is "as sent by the app, before TLS". Keep that label.
- Keep the footer disclaimer visible in all modes.
- No em dashes in user-facing copy. Concise, professional, direct tone.

## Commands
- Run: `uvicorn app.main:app --reload`
- Tests: `pytest -q`
- Mock mode: `DEMO_MODE=mock uvicorn app.main:app`
- Generate large doc: `python scripts/make_large_doc.py`

## Definition of done
All P0 requirements and acceptance criteria AC-01 to AC-07 in the FRD pass.
Work phase by phase from the build phases list. Run tests after each phase.
```

## 17. Open Questions

1. Which hosted provider and model for the live side?
2. Which local model and what is the demo laptop spec (RAM, GPU)?
3. Live run or recorded clip as the default on the day?
4. Should the dashboard follow the Citadel Quantum Consortium design tokens exactly?
5. Is the Arabic and local-context comparison worth adding as a second scene?
6. Where does the demo sit in the deck: end of Sovereignty pillar or end of section?

## 18. First Prompt to Give Claude Code

> Read `sovereignty-demo-dashboard.md` and `CLAUDE.md`. Start with Phase 0 and Phase 1 only. Scaffold the FastAPI project, implement the provider adapter interface, MockAdapter, orchestrator and WebSocket event stream, plus tests for AC-01. Stop and summarise before starting Phase 2.
