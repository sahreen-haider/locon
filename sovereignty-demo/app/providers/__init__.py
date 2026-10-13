from __future__ import annotations

from app.config import Settings
from app.providers.base import ProviderAdapter
from app.providers.mock import mock_hosted, mock_local
from app.providers.ollama import OllamaAdapter
from app.providers.openai_like import OpenAIAdapter


class ProviderUnavailable(RuntimeError):
    pass


def build_adapters(settings: Settings) -> dict[str, ProviderAdapter]:
    """Adapters for the two panels, keyed 'local' and 'hosted'."""
    if settings.mode == "mock":
        return {
            "local": mock_local(settings.mock_token_delay_s),
            "hosted": mock_hosted(settings.mock_token_delay_s),
        }
    if settings.hosted_provider != "openai":
        raise ProviderUnavailable(f"Hosted provider '{settings.hosted_provider}' is not implemented. Use openai.")
    return {
        "local": OllamaAdapter(settings.ollama_url, settings.local_model),
        "hosted": OpenAIAdapter(settings.openai_base_url, settings.hosted_model),
    }
