"""Handoff state schema validation (warn-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import ValidationError

SCHEMA_PATH = Path(__file__).parent / "handoff-state.schema.json"


def load_schema() -> dict[str, Any]:
    """Load the bundled handoff-state JSON Schema."""
    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _format_validation_error(error: ValidationError) -> str:
    """Format a jsonschema error with a dotted property path."""
    path = ".".join(str(part) for part in error.absolute_path)
    location = f" at {path}" if path else ""
    return f"{error.message}{location}"


def validate_handoff_state(state: dict[str, Any]) -> list[str]:
    """Return validation warnings for handoff state (non-blocking)."""
    schema = load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    return [
        _format_validation_error(error)
        for error in sorted(validator.iter_errors(state), key=lambda e: e.path)
    ]
