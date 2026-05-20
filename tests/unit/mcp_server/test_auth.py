from __future__ import annotations

import asyncio

import pytest

from mcp_server.auth import (
    TOKEN_ENV,
    StaticBearerVerifier,
    get_static_verifier,
)


def test_verifier_accepts_matching_token() -> None:
    verifier = StaticBearerVerifier("secret")
    result = asyncio.run(verifier.verify_token("secret"))
    assert result is not None
    assert result.token == "secret"


def test_verifier_rejects_mismatched_token() -> None:
    verifier = StaticBearerVerifier("secret")
    result = asyncio.run(verifier.verify_token("wrong"))
    assert result is None


def test_verifier_rejects_empty_token() -> None:
    verifier = StaticBearerVerifier("secret")
    result = asyncio.run(verifier.verify_token(""))
    assert result is None


def test_verifier_constructor_rejects_empty_configured_token() -> None:
    with pytest.raises(RuntimeError, match=TOKEN_ENV):
        StaticBearerVerifier("")


def test_get_static_verifier_raises_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    with pytest.raises(RuntimeError, match=TOKEN_ENV):
        get_static_verifier()


def test_get_static_verifier_raises_when_env_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TOKEN_ENV, "")
    with pytest.raises(RuntimeError, match=TOKEN_ENV):
        get_static_verifier()


def test_get_static_verifier_returns_verifier_with_env_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TOKEN_ENV, "fromenv")
    verifier = get_static_verifier()
    assert isinstance(verifier, StaticBearerVerifier)
