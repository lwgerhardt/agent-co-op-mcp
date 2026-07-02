"""Tests for project manifests — init, summary, routing overrides, prompts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_co_op.handoff import publish
from agent_co_op.projects import (
    init_project,
    init_workspace,
    load_project,
    pickup,
    project_summary,
    role_prompt,
)
from agent_co_op.routing import resolve_routing


def _write_manifest(tmp_path: Path, project_id: str, manifest: dict) -> None:
    d = tmp_path / ".agent-co-op"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{project_id}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


class TestLoadProject:
    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert load_project("missing", base=tmp_path) is None

    def test_loads_project_specific_manifest(self, tmp_path: Path) -> None:
        _write_manifest(
            tmp_path,
            "my-saas",
            {"id": "my-saas", "name": "My SaaS App", "roles": {}},
        )
        project = load_project("my-saas", base=tmp_path)
        assert project is not None
        assert project["name"] == "My SaaS App"

    def test_falls_back_to_project_json(self, tmp_path: Path) -> None:
        d = tmp_path / ".agent-co-op"
        d.mkdir(parents=True, exist_ok=True)
        (d / "project.json").write_text(
            json.dumps({"id": "shared", "name": "Shared Project"}),
            encoding="utf-8",
        )
        project = load_project("anything", base=tmp_path)
        assert project is not None
        assert project["name"] == "Shared Project"


class TestInitProject:
    def test_creates_manifest(self, tmp_path: Path) -> None:
        path = init_project("my-app", name="My App", base=tmp_path)
        assert path.exists()
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert manifest["id"] == "my-app"
        assert manifest["name"] == "My App"
        assert "planner" in manifest["roles"]

    def test_refuses_overwrite(self, tmp_path: Path) -> None:
        init_project("my-app", base=tmp_path)
        with pytest.raises(FileExistsError):
            init_project("my-app", base=tmp_path)


class TestInitWorkspace:
    def test_creates_manifest(self, tmp_path: Path) -> None:
        result = init_workspace("my-app", name="My App", base=tmp_path)
        assert (tmp_path / ".agent-co-op" / "my-app.json").exists()
        assert result["project_id"] == "my-app"
        assert len(result["next_commands"]) == 3

    def test_updates_gitignore(self, tmp_path: Path) -> None:
        result = init_workspace("my-app", base=tmp_path)
        assert result["gitignore_updated"] is True
        gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert ".agent-co-op/handoff-state.json" in gitignore
        assert "# agent-co-op handoff state" in gitignore

    def test_skips_gitignore_when_disabled(self, tmp_path: Path) -> None:
        result = init_workspace("my-app", update_gitignore=False, base=tmp_path)
        assert result["gitignore_updated"] is False
        assert not (tmp_path / ".gitignore").exists()

    def test_gitignore_is_idempotent(self, tmp_path: Path) -> None:
        init_workspace("my-app", base=tmp_path)
        result = init_workspace("other-app", base=tmp_path)
        assert result["gitignore_updated"] is False

    def test_refuses_duplicate_manifest(self, tmp_path: Path) -> None:
        init_workspace("my-app", base=tmp_path)
        with pytest.raises(FileExistsError):
            init_workspace("my-app", base=tmp_path)


class TestProjectSummary:
    def test_raises_when_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No project manifest found"):
            project_summary("missing", base=tmp_path)

    def test_returns_summary(self, tmp_path: Path) -> None:
        init_project("my-app", name="My App", description="Demo", base=tmp_path)
        summary = project_summary("my-app", base=tmp_path)
        assert summary["id"] == "my-app"
        assert summary["name"] == "My App"
        assert summary["description"] == "Demo"
        assert "planner" in summary["roles"]


class TestProjectRoutingOverrides:
    def test_role_agent_override(self, tmp_path: Path) -> None:
        _write_manifest(
            tmp_path,
            "my-saas",
            {
                "id": "my-saas",
                "roles": {"planner": {"agent": "cursor", "model_tier": "low"}},
            },
        )
        info = resolve_routing("planner", project_id="my-saas", base=tmp_path)
        assert info["agent"] == "cursor"
        assert info["model_tier"] == "low"

    def test_role_work_mode_override(self, tmp_path: Path) -> None:
        _write_manifest(
            tmp_path,
            "my-saas",
            {"id": "my-saas", "roles": {"planner": {"work_mode": "longContext"}}},
        )
        info = resolve_routing("planner", project_id="my-saas", base=tmp_path)
        assert info["work_mode"] == "longContext"
        assert "Scouting" in info["work_mode_description"]

    def test_invalid_work_mode_raises(self, tmp_path: Path) -> None:
        _write_manifest(
            tmp_path,
            "my-saas",
            {"id": "my-saas", "roles": {"planner": {"work_mode": "turbo"}}},
        )
        with pytest.raises(ValueError, match="Unknown work_mode"):
            resolve_routing("planner", project_id="my-saas", base=tmp_path)


class TestProjectRolePrompt:
    def test_includes_project_metadata(self, tmp_path: Path) -> None:
        _write_manifest(
            tmp_path,
            "my-saas",
            {
                "id": "my-saas",
                "name": "My SaaS App",
                "description": "Team collaboration app",
                "repository": "https://github.com/example/my-saas",
                "roles": {},
            },
        )
        result = role_prompt("my-saas", "planner", base=tmp_path)
        assert "My SaaS App" in result
        assert "Team collaboration app" in result
        assert "https://github.com/example/my-saas" in result

    def test_includes_role_notes(self, tmp_path: Path) -> None:
        _write_manifest(
            tmp_path,
            "my-saas",
            {
                "id": "my-saas",
                "roles": {
                    "planner": {"notes": "Focus on API design and data model first"}
                },
            },
        )
        result = role_prompt("my-saas", "planner", base=tmp_path)
        assert "Focus on API design and data model first" in result

    def test_pickup_uses_project_context(self, tmp_path: Path) -> None:
        _write_manifest(
            tmp_path,
            "my-saas",
            {
                "id": "my-saas",
                "name": "My SaaS App",
                "roles": {
                    "verifier": {"notes": "Run unit tests before marking done"}
                },
            },
        )
        publish("Implement auth", "implement", "my-saas", base=tmp_path)
        result = pickup(base=tmp_path)
        assert "My SaaS App" in result
        assert "Run unit tests before marking done" in result
