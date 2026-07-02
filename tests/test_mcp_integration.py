"""Tests for MCP tool and resource handlers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_co_op.mcp_server import (
    handoff_clear,
    handoff_publish,
    handoff_status,
    resource_handoff_current,
    resource_handoff_project,
    resource_handoff_state,
    resource_handoff_status,
)
from agent_co_op.projects import init_project

from git_helpers import init_git_repo, requires_git


class TestMcpTools:
    def test_handoff_status_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        payload = json.loads(handoff_status())
        assert payload["active"] is False
        assert payload["has_state"] is False

    def test_publish_clear_round_trip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        handoff_publish(
            objective="Build feature",
            phase="plan",
            project_id="my-app",
        )
        status = json.loads(handoff_status())
        assert status["active"] is True
        assert status["objective"] == "Build feature"

        handoff_clear()
        status = json.loads(handoff_status())
        assert status["has_state"] is False


class TestMcpResources:
    @requires_git
    def test_status_resource(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        init_git_repo(tmp_path)
        init_project("my-app", base=tmp_path)
        handoff_publish(objective="Plan", phase="plan", project_id="my-app")

        payload = json.loads(resource_handoff_status())
        assert payload["active"] is True
        assert payload["phase"] == "plan"

    def test_current_resource_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        payload = json.loads(resource_handoff_current())
        assert payload["error"] == "No active handoff."

    def test_state_resource(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        handoff_publish(objective="Work", phase="implement", project_id="my-app")

        payload = json.loads(resource_handoff_state())
        assert payload["objective"] == "Work"
        assert "git" not in payload

    def test_project_resource(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        init_project("my-app", name="My App", base=tmp_path)

        payload = json.loads(resource_handoff_project("my-app"))
        assert payload["id"] == "my-app"
        assert payload["name"] == "My App"

    def test_project_resource_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        payload = json.loads(resource_handoff_project("missing"))
        assert "error" in payload
