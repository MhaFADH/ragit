from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse

_HOST_TOKEN_USERS: dict[str, str] = {
    "github.com": "x-access-token",
    "bitbucket.org": "x-token-auth",
    "gitlab.com": "oauth2",
}


def repo_name_from_url(url: str) -> str:
    basename = url.rstrip("/").rsplit("/", 1)[-1]
    return basename.removesuffix(".git") or basename


def _inject_token(url: str, token: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Token auth requires an https:// URL; got: {url}")
    host = parsed.hostname or ""
    if host not in _HOST_TOKEN_USERS:
        raise ValueError(
            f"Unsupported git host '{host}'. Supported: {', '.join(sorted(_HOST_TOKEN_USERS))}."
        )
    return f"https://{_HOST_TOKEN_USERS[host]}:{token}@{url[len('https://') :]}"


def shallow_clone(
    url: str,
    dest: Path,
    branch: str = "",
    *,
    token: str | None = None,
) -> None:
    clone_url = _inject_token(url, token) if token else url
    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd += ["--branch", branch]
    cmd += [clone_url, str(dest)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
