from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError


class PayloadValidationError(ValueError):
    """Raised when a task payload does not satisfy its capability schema."""


def validate_payload(payload: Any, schema: dict[str, Any]) -> None:
    """Validate a payload against a capability's JSON Schema.

    Capability schemas are operator-provided data, so invalid schemas are
    reported as configuration errors rather than being exposed as payload
    failures. Only the first deterministic validation error is returned to the
    caller to keep the API response concise.
    """
    try:
        validator = Draft202012Validator(schema)
        validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError("Invalid capability input schema") from exc

    error = next(iter(sorted(validator.iter_errors(payload), key=lambda item: list(item.path))), None)
    if error is not None:
        location = ".".join(str(part) for part in error.path)
        suffix = f" at {location}" if location else ""
        raise PayloadValidationError(f"PAYLOAD_INVALID: {error.message}{suffix}") from error
