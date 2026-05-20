from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from docs_rag.repo_diff.utils.git_ops import (
    _inject_token,
    redact_url,
    repo_name_from_url,
    shallow_clone,
)


def test_repo_name_strips_dot_git() -> None:
    assert repo_name_from_url("https://bitbucket.org/org/foo.git") == "foo"


def test_repo_name_no_suffix() -> None:
    assert repo_name_from_url("https://github.com/org/bar") == "bar"


def test_repo_name_trailing_slash() -> None:
    assert repo_name_from_url("https://github.com/org/bar/") == "bar"


def test_inject_token_github() -> None:
    out = _inject_token("https://github.com/org/foo.git", "ghp_abc")
    assert out == "https://x-access-token:ghp_abc@github.com/org/foo.git"


def test_inject_token_bitbucket() -> None:
    out = _inject_token("https://bitbucket.org/org/foo.git", "bb_abc")
    assert out == "https://x-token-auth:bb_abc@bitbucket.org/org/foo.git"


def test_inject_token_gitlab() -> None:
    out = _inject_token("https://gitlab.com/org/foo.git", "gl_abc")
    assert out == "https://oauth2:gl_abc@gitlab.com/org/foo.git"


def test_inject_token_rejects_unknown_host() -> None:
    with pytest.raises(ValueError, match="Unsupported git host"):
        _inject_token("https://git.example.com/org/foo.git", "tok")


def test_inject_token_rejects_ssh() -> None:
    with pytest.raises(ValueError, match="https://"):
        _inject_token("git@bitbucket.org:org/foo.git", "abc")


def test_inject_token_rejects_http() -> None:
    with pytest.raises(ValueError, match="https://"):
        _inject_token("http://bitbucket.org/org/foo.git", "abc")


def test_redact_url_strips_userinfo() -> None:
    assert (
        redact_url("https://x-access-token:ghp_secret@github.com/org/foo.git")
        == "https://github.com/org/foo.git"
    )


def test_redact_url_passthrough_when_no_credentials() -> None:
    assert redact_url("https://github.com/org/foo.git") == "https://github.com/org/foo.git"


def test_redact_url_passthrough_for_non_url() -> None:
    assert redact_url("not-a-url") == "not-a-url"


def test_shallow_clone_failure_redacts_token_in_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(cmd: list[str], **_: object) -> None:
        raise subprocess.CalledProcessError(returncode=128, cmd=cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        shallow_clone(
            "https://github.com/org/foo.git",
            Path("/tmp/ragit_test_target"),
            token="ghp_secret",
        )
    rendered = " ".join(exc_info.value.cmd)
    assert "ghp_secret" not in rendered
    assert "x-access-token" not in rendered
