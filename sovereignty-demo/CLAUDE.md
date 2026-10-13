# Sovereignty Demo Dashboard

## What this is
Split-screen demo: local open-weight model vs hosted API, with live network
instrumentation. For an executive workshop. Illustrative, fictional data only.
Full spec: `../sovereignty-demo-dashboard.md`.

## Rules
- Never use real company data or real secrets. Only the bundled fictional documents.
- API keys come from environment variables. Never commit .env.
- Do not log document contents or API keys.
- All provider HTTP traffic must go through NetworkMeter. No direct httpx/requests calls in adapters.
- Payload view is "as sent by the app, before TLS". Keep that label.
- Keep the footer disclaimer visible in all modes.
- No em dashes in user-facing copy. Concise, professional, direct tone.

## Commands
- Run (live, reads .env): `uvicorn app.main:app --env-file .env`
- Tests: `pytest -q`
- Mock mode: `DEMO_MODE=mock uvicorn app.main:app`
- Generate large doc: `python scripts/make_large_doc.py`

## Definition of done
All P0 requirements and acceptance criteria AC-01 to AC-07 in the FRD pass.
Work phase by phase from the build phases list. Run tests after each phase.
