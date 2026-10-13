"""Settings, environment and canary list.

API keys are never stored on Settings. They are read from the environment at the
point of use, and only their presence is ever reported.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"

DEFAULT_CANARIES = ["Project Falcon", "Zentra Ltd", "USD 212M", "BM-7731-KX"]

Mode = Literal["mock", "live"]
HostedProvider = Literal["openai", "anthropic", "gemini"]

API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


class Settings(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    mode: Mode = "mock"
    ollama_url: str = "http://localhost:11434"
    local_model: str = "qwen2.5:0.5b"
    hosted_provider: HostedProvider = "openai"
    hosted_model: str = "gpt-4.1-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    offline_sim: bool = False
    panel_timeout_s: float = Field(default=30.0, gt=0)
    mock_token_delay_s: float = Field(default=0.04, ge=0)
    canaries: list[str] = Field(default_factory=lambda: list(DEFAULT_CANARIES))

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        values: dict[str, object] = {
            "mode": env.get("DEMO_MODE"),
            "ollama_url": env.get("OLLAMA_URL"),
            "local_model": env.get("LOCAL_MODEL"),
            "hosted_provider": env.get("HOSTED_PROVIDER"),
            "hosted_model": env.get("HOSTED_MODEL"),
            "openai_base_url": env.get("OPENAI_BASE_URL"),
            "panel_timeout_s": env.get("PANEL_TIMEOUT_S"),
            "mock_token_delay_s": env.get("MOCK_TOKEN_DELAY_S"),
        }
        return cls(**{k: v for k, v in values.items() if v})

    def public(self) -> dict:
        """Config as exposed by GET /api/config."""
        return self.model_dump()


class ConfigUpdate(BaseModel):
    """Body of POST /api/config. Unknown keys are rejected."""

    model_config = ConfigDict(extra="forbid")

    mode: Mode | None = None
    local_model: str | None = None
    hosted_provider: HostedProvider | None = None
    hosted_model: str | None = None
    offline_sim: bool | None = None
    canaries: list[str] | None = None


def api_key_present(provider: str) -> bool:
    return bool(os.environ.get(API_KEY_ENV[provider]))
