import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


def test_from_env(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "live")
    monkeypatch.setenv("HOSTED_PROVIDER", "anthropic")
    monkeypatch.setenv("PANEL_TIMEOUT_S", "12")
    s = Settings.from_env()
    assert (s.mode, s.hosted_provider, s.panel_timeout_s) == ("live", "anthropic", 12)


def test_from_env_rejects_bad_mode(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "demo")
    with pytest.raises(ValidationError):
        Settings.from_env()


def test_config_contains_no_api_keys(monkeypatch, mock_settings):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    with TestClient(create_app(mock_settings)) as client:
        assert "sk-test-secret" not in client.get("/api/config").text
        health = client.get("/api/health").json()
        assert health["api_keys"]["openai"] is True
        assert "sk-test-secret" not in str(health)


@pytest.mark.parametrize("body", [{"mode": "demo"}, {"hosted_provider": "acme"}, {"api_key": "x"}])
def test_config_update_rejects_invalid(body, mock_settings):
    with TestClient(create_app(mock_settings)) as client:
        assert client.post("/api/config", json=body).status_code == 422


def test_config_update_applies(mock_settings):
    with TestClient(create_app(mock_settings)) as client:
        resp = client.post("/api/config", json={"offline_sim": True, "hosted_provider": "gemini"})
        assert resp.status_code == 200
        cfg = client.get("/api/config").json()
        assert cfg["offline_sim"] is True and cfg["hosted_provider"] == "gemini"


def test_documents_listed(mock_settings):
    with TestClient(create_app(mock_settings)) as client:
        ids = {d["id"] for d in client.get("/api/documents").json()}
        assert {"memo_small", "proposal_poisoned"} <= ids


def test_memo_contains_all_canaries():
    from app.documents import load_document

    memo = load_document("memo_small")
    assert all(c in memo for c in Settings().canaries)
