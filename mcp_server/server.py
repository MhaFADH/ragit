from __future__ import annotations

from typing import Any

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from mcp_server.auth import get_static_verifier
from mcp_server.repos import index_status as repos_index_status
from mcp_server.repos import list_repos as repos_list_repos


def create_app() -> FastMCP:
    server = FastMCP(
        "ragit",
        host="0.0.0.0",
        port=8000,
        token_verifier=get_static_verifier(),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl("http://localhost:8000"),
            resource_server_url=AnyHttpUrl("http://localhost:8000"),
            required_scopes=[],
        ),
    )

    @server.tool()
    def list_repos() -> list[dict[str, Any]]:
        """List indexed repositories with file counts per (repo, branch)."""
        return repos_list_repos()

    @server.tool()
    def index_status() -> list[dict[str, Any]]:
        """Per-(repo, branch) index status: file count, chunk count, total tokens."""
        return repos_index_status()

    return server


def main() -> None:
    create_app().run(transport="streamable-http")


if __name__ == "__main__":
    main()
