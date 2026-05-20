from __future__ import annotations

import pytest
from docs_rag.repo_diff.get_repos import get_repos


def _call(monkeypatch: pytest.MonkeyPatch, returned: object) -> object:
    from airflow.sdk import Variable

    def fake_get(key: str, default: object = ..., deserialize_json: bool = False) -> object:
        if returned is _MISSING:
            return default
        return returned

    monkeypatch.setattr(Variable, "get", fake_get)
    return get_repos.function()


_MISSING = object()


def test_get_repos_returns_loaded_list(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [{"url": "https://bitbucket.org/org/foo.git"}]
    assert _call(monkeypatch, payload) == payload


def test_get_repos_raises_when_variable_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RuntimeError, match="not set"):
        _call(monkeypatch, _MISSING)


def test_get_repos_raises_when_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RuntimeError, match="non-empty"):
        _call(monkeypatch, [])


def test_get_repos_raises_when_not_a_list(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RuntimeError, match="non-empty"):
        _call(monkeypatch, {"url": "x"})
