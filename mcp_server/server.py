from __future__ import annotations

from typing import Any

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from mcp_server.auth import get_static_verifier
from mcp_server.repos import index_status as repos_index_status
from mcp_server.repos import list_repos as repos_list_repos
from mcp_server.search import search as search_pipeline


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

    @server.tool()
    def search_docs(
        query: str,
        top_k: int = 5,
        repo: str | None = None,
        branch: str = "main",
    ) -> list[dict[str, Any]]:
        """Semantic search over indexed markdown chunks. Returns ranked excerpts.

        Args:
            query: natural-language question or keyword phrase.
            top_k: maximum number of chunks to return (default 5, max 50).
            repo: optional repo-name filter (e.g. "foo" matches a repo named "foo").
            branch: branch to search (default "main"). Must match the branch value
                stored at ingestion time. Repos ingested without an explicit branch
                are stored with branch="" — pass branch="" to reach those.
        """
        return search_pipeline(query, top_k=top_k, repo=repo, branch=branch)

    return server


def main() -> None:
    create_app().run(transport="streamable-http")


if __name__ == "__main__":
    main()
