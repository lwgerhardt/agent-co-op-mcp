"""Tests for MCP tool and resource handlers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from git_helpers import init_git_repo, requires_git
from mcp.server.fastmcp.exceptions import ResourceError, ToolError

from agent_co_op.mcp_server import (
    handoff_clear,
    handoff_publish,
    handoff_status,
    resource_handoff_current,
    resource_handoff_project,
    resource_handoff_queue,
    resource_handoff_report,
    resource_handoff_state,
    resource_handoff_status,
)
from agent_co_op.projects import init_project


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

    def test_pickup_without_handoff_raises_tool_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agent_co_op.mcp_server import handoff_pickup

        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        with pytest.raises(ToolError, match="No handoff state found"):
            handoff_pickup()


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
        with pytest.raises(ResourceError, match="No active handoff"):
            resource_handoff_current()

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
        with pytest.raises(ResourceError, match="No project manifest found"):
            resource_handoff_project("missing")

    def test_run_verification_tool(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agent_co_op.mcp_server import handoff_run_verification

        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        queue = {
            "version": "1.0",
            "profile_id": "default",
            "project_id": "my-app",
            "commands": [{"id": "ok", "label": "Pass", "command": "true"}],
        }
        (tmp_path / ".agent-co-op").mkdir(parents=True)
        (tmp_path / ".agent-co-op" / "verification-queue.json").write_text(
            json.dumps(queue), encoding="utf-8"
        )
        payload = json.loads(handoff_run_verification())
        assert payload["overall"] == "PASS"

    def test_queue_resource_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        with pytest.raises(ResourceError, match="No verification queue found"):
            resource_handoff_queue()

    def test_report_resource_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        with pytest.raises(ResourceError, match="No verification report found"):
            resource_handoff_report()

    def test_report_resource_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agent_co_op.verification import run_verification, write_queue

        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        write_queue(
            {
                "version": "1.0",
                "profile_id": "default",
                "project_id": "my-app",
                "commands": [{"id": "ok", "label": "Pass", "command": "true"}],
            },
            base=tmp_path,
        )
        run_verification(base=tmp_path)
        payload = json.loads(resource_handoff_report())
        assert payload["overall"] == "PASS"

    def test_publish_for_verifier_structured_context(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agent_co_op.handoff import read_state
        from agent_co_op.mcp_server import handoff_publish_for_verifier

        monkeypatch.setenv("AGENT_CO_OP_ROOT", str(tmp_path))
        init_project("my-app", base=tmp_path)
        manifest_path = tmp_path / ".agent-co-op" / "my-app.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["verification"] = {
            "profiles": {
                "default": {
                    "commands": [{"id": "ok", "label": "Pass", "command": "true"}]
                }
            }
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        context = {
            "read_map": [{"file": "src/app.py", "lines": "1-10", "why": "entry"}],
            "blockers": ["Needs review"],
        }
        payload = json.loads(
            handoff_publish_for_verifier(
                objective="Verify auth",
                project_id="my-app",
                context=context,
            )
        )
        assert payload["status"] == "published"
        state = read_state(base=tmp_path)
        assert isinstance(state["context"], dict)
        assert state["context"]["blockers"] == ["Needs review"]
