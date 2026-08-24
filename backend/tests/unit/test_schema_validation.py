from __future__ import annotations

import pytest

from app.core.schema_validation import PayloadValidationError, validate_payload
from app.services.messaging import MessagingService


def test_validate_payload_accepts_matching_payload() -> None:
    validate_payload(
        {"text": "hello"},
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    )


def test_validate_payload_reports_protocol_error_code() -> None:
    with pytest.raises(PayloadValidationError, match=r"^PAYLOAD_INVALID:"):
        validate_payload(
            {"text": 42},
            {"type": "object", "properties": {"text": {"type": "string"}}},
        )


def test_validate_payload_rejects_malformed_capability_schema() -> None:
    with pytest.raises(ValueError, match="Invalid capability input schema"):
        validate_payload({"text": "hello"}, {"type": "not-a-json-schema-type"})


def test_capability_schema_lookup_matches_capability_name() -> None:
    from types import SimpleNamespace

    agent = SimpleNamespace(
        capabilities=[
            {"name": "summarize", "input_schema": {"type": "object"}},
            {"name": "translate", "input_schema": {"type": "string"}},
        ]
    )
    assert MessagingService._capability_input_schema(agent, "translate") == {"type": "string"}
    assert MessagingService._capability_input_schema(agent, "missing") is None
