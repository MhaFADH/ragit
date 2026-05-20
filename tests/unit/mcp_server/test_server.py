from __future__ import annotations

import pytest

from mcp_server.auth import TOKEN_ENV


def test_create_app_succeeds_with_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV, "test-token")
    from mcp_server.server import create_app

    server = create_app()
    assert server.name == "ragit"


def test_create_app_fails_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    from mcp_server.server import create_app

    with pytest.raises(RuntimeError, match=TOKEN_ENV):
        create_app()
