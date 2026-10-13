import socket

import pytest

from app.config import Settings


@pytest.fixture
def no_network(monkeypatch):
    """Fail any attempt to open an IP connection, so 'works offline' is actually tested."""

    def blocked(self, *args, **kwargs):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            raise OSError("network access blocked by test")
        return original_connect(self, *args, **kwargs)

    original_connect = socket.socket.connect
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
def mock_settings():
    return Settings(mode="mock", mock_token_delay_s=0.001, panel_timeout_s=5)
