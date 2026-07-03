"""JSON Schema validation for agent-co-op project manifests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import ValidationError

SCHEMA_PATH = Path(__file__).parent / "project-manifest.schema.json"
_EXTENSION_KEY = re.compile(r"^x-")


def load_schema() -> dict[str, Any]:
    """Load and return the bundled project manifest JSON Schema."""
    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def known_manifest_keys() -> frozenset[str]:
    """Return top-level manifest keys defined in the JSON Schema."""
    schema = load_schema()
    return frozenset(schema.get("properties", {}).keys())


def _format_validation_error(error: ValidationError) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    location = f" at {path}" if path else ""
    return f"{error.message}{location}"


def _unknown_key_warnings(manifest: dict[str, Any]) -> list[str]:
    known = known_manifest_keys()
    warnings: list[str] = []
    for key in manifest:
        if key in known or _EXTENSION_KEY.match(key):
            continue
        warnings.append(
            f"Unknown manifest key {key!r} (ignored; use an x- prefix for extensions)"
        )
    return warnings


def _manifest_for_schema_validation(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return a copy containing only schema-known and x- extension keys."""
    known = known_manifest_keys()
    return {
        key: value
        for key, value in manifest.items()
        if key in known or _EXTENSION_KEY.match(key)
    }


def _semantic_errors(
    manifest: dict[str, Any],
    *,
    expected_id: str | None = None,
) -> list[str]:
    errors: list[str] = []
    manifest_id = manifest.get("id")
    if expected_id is not None and manifest_id != expected_id:
        errors.append(
            f"id {manifest_id!r} does not match expected project id {expected_id!r}"
        )
    return errors


def validate_manifest_data(
    manifest: Any,
    *,
    expected_id: str | None = None,
) -> dict[str, Any]:
    """Validate a parsed manifest object.

    Returns a report dict with keys: valid, errors, warnings, id, roles.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(manifest, dict):
        return {
            "valid": False,
            "errors": ["Manifest must be a JSON object."],
            "warnings": warnings,
            "id": None,
            "roles": [],
        }

    warnings.extend(_unknown_key_warnings(manifest))

    schema = load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    for error in sorted(
        validator.iter_errors(_manifest_for_schema_validation(manifest)),
        key=lambda e: e.path,
    ):
        errors.append(_format_validation_error(error))

    errors.extend(_semantic_errors(manifest, expected_id=expected_id))

    roles_obj = manifest.get("roles", {})
    roles = sorted(roles_obj.keys()) if isinstance(roles_obj, dict) else []

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "id": manifest.get("id"),
        "roles": roles,
    }


def load_manifest_json(path: Path) -> dict[str, Any]:
    """Load and parse a manifest JSON file.

    Raises ValueError for invalid JSON or non-object root values.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Manifest must be a JSON object: {path}")
    return data


def validate_manifest_file(
    path: Path,
    *,
    expected_id: str | None = None,
) -> dict[str, Any]:
    """Validate a manifest file on disk."""
    manifest = load_manifest_json(path)
    report = validate_manifest_data(manifest, expected_id=expected_id)
    report["manifest_path"] = str(path)
    return report
