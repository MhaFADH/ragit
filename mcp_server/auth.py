from __future__ import annotations

import hmac
import os

from mcp.server.auth.provider import AccessToken, TokenVerifier

TOKEN_ENV = "RAGIT_MCP_TOKEN"


class StaticBearerVerifier(TokenVerifier):
    def __init__(self, token: str) -> None:
        if not token:
            raise RuntimeError(f"{TOKEN_ENV} must be a non-empty string")
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if hmac.compare_digest(token, self._token):
            return AccessToken(token=token, client_id="static", scopes=[])
        return None


def get_static_verifier() -> StaticBearerVerifier:
    token = os.environ.get(TOKEN_ENV, "")
    if not token:
        raise RuntimeError(
            f"{TOKEN_ENV} not set. Generate one with `openssl rand -hex 32` "
            "and add it to your .env file."
        )
    return StaticBearerVerifier(token)
