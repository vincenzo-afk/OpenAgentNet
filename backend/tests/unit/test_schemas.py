from __future__ import annotations

import pytest
from app.schemas.agent import AgentManifest, CapabilitySchema, RegistrationRequest


class TestAgentSchemas:
    def test_capability_schema(self):
        cap = CapabilitySchema(
            name="summarize",
            description="Summarizes text",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        )
        assert cap.name == "summarize"
        assert cap.tags == []

    def test_agent_manifest(self):
        manifest = AgentManifest(
            name="test-agent",
            version="1.0.0",
            description="A test agent",
            owner={"id": "user-123", "type": "user"},
            capabilities=[
                CapabilitySchema(
                    name="test",
                    description="Test capability",
                    input_schema={},
                    output_schema={},
                )
            ],
            endpoint="https://example.com/agent",
            public_key="ed25519:test",
        )
        assert manifest.protocol_version == "0.1.0"
        assert len(manifest.capabilities) == 1

    def test_registration_request(self):
        req = RegistrationRequest(
            identity=AgentManifest(
                name="test-agent",
                version="1.0.0",
                description="Test",
                owner={"id": "u1", "type": "user"},
                capabilities=[],
                endpoint="https://example.com",
                public_key="ed25519:test",
            ),
            proof={"timestamp": "2025-01-01T00:00:00Z", "signature": "base64url:test"},
        )
        assert req.identity.name == "test-agent"
