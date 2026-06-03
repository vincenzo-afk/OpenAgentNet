from __future__ import annotations

import pytest
from datetime import datetime, timezone

from app.core.security import create_access_token, create_refresh_token, decode_token


class TestJWT:
    def test_create_access_token(self):
        token = create_access_token(
            subject="did:oan:test123",
            scopes=["agent:all"],
            extra_claims={"agent_id": "test123"},
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self):
        token = create_access_token(
            subject="did:oan:test123",
            scopes=["agent:all"],
        )
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "did:oan:test123"
        assert "agent:all" in payload["scopes"]
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        token = create_refresh_token(subject="did:oan:test123")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "did:oan:test123"
        assert payload["type"] == "refresh"

    def test_decode_invalid_token(self):
        payload = decode_token("invalid.token.here")
        assert payload is None

    def test_token_with_scopes(self):
        token = create_access_token(
            subject="test",
            scopes=["read", "write"],
        )
        payload = decode_token(token)
        assert "read" in payload["scopes"]
        assert "write" in payload["scopes"]
