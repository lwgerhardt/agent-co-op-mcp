"""Tests for project manifest JSON Schema validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_co_op.manifest import (
    load_manifest_json,
    load_schema,
    validate_manifest_data,
    validate_manifest_file,
)
from agent_co_op.projects import init_project, validate_project


class TestLoadSchema:
    def test_schema_has_required_fields(self) -> None:
        schema = load_schema()
        assert schema["type"] == "object"
        assert "id" in schema["required"]
        assert "roles" in schema["properties"]


class TestValidateManifestData:
    def test_valid_example_manifest(self) -> None:
        example = json.loads(
            Path("examples/project.example.json").read_text(encoding="utf-8")
        )
        report = validate_manifest_data(example, expected_id="my-saas")
        assert report["valid"] is True
        assert report["errors"] == []
        assert report["roles"] == ["planner", "scaffold", "verifier"]

    def test_missing_id(self) -> None:
        report = validate_manifest_data({"name": "No id"})
        assert report["valid"] is False
        assert any("id" in error for error in report["errors"])

    def test_unknown_top_level_field(self) -> None:
        report = validate_manifest_data({"id": "x", "extra": True})
        assert report["valid"] is False

    def test_unknown_role_key(self) -> None:
        report = validate_manifest_data(
            {"id": "x", "roles": {"ghost": {"notes": "nope"}}}
        )
        assert report["valid"] is False
        assert any("ghost" in error or "propertyNames" in error for error in report["errors"])

    def test_invalid_work_mode(self) -> None:
        report = validate_manifest_data(
            {"id": "x", "roles": {"planner": {"work_mode": "turbo"}}}
        )
        assert report["valid"] is False

    def test_invalid_model_tier(self) -> None:
        report = validate_manifest_data(
            {"id": "x", "roles": {"planner": {"model_tier": "ultra"}}}
        )
        assert report["valid"] is False

    def test_expected_id_mismatch(self) -> None:
        report = validate_manifest_data({"id": "other"}, expected_id="my-saas")
        assert report["valid"] is False
        assert any("does not match" in error for error in report["errors"])

    def test_non_object_root(self) -> None:
        report = validate_manifest_data(["not", "an", "object"])
        assert report["valid"] is False
        assert report["errors"] == ["Manifest must be a JSON object."]


class TestValidateManifestFile:
    def test_valid_file(self, tmp_path: Path) -> None:
        init_project("my-app", name="My App", base=tmp_path)
        path = tmp_path / ".agent-co-op" / "my-app.json"
        report = validate_manifest_file(path, expected_id="my-app")
        assert report["valid"] is True

    def test_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_manifest_json(path)


class TestValidateProject:
    def test_valid_project(self, tmp_path: Path) -> None:
        init_project("my-app", base=tmp_path)
        report = validate_project("my-app", base=tmp_path)
        assert report["valid"] is True

    def test_missing_project(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No project manifest found"):
            validate_project("missing", base=tmp_path)

    def test_id_mismatch(self, tmp_path: Path) -> None:
        init_project("my-app", base=tmp_path)
        path = tmp_path / ".agent-co-op" / "my-app.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["id"] = "wrong-id"
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        report = validate_project("my-app", base=tmp_path)
        assert report["valid"] is False
