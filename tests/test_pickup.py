"""Tests for pickup and role_prompt — inference from handoff state."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_co_op.handoff import publish
from agent_co_op.projects import pickup, role_prompt


class TestPickup:
    def test_raises_when_no_state(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No handoff state found"):
            pickup(base=tmp_path)

    def test_returns_string_with_state(self, tmp_path: Path) -> None:
        publish("Build the feature", "implement", "my-project", base=tmp_path)
        result = pickup(base=tmp_path)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_role(self, tmp_path: Path) -> None:
        publish("Build the feature", "implement", "my-project", base=tmp_path)
        result = pickup(base=tmp_path)
        assert "verifier" in result

    def test_contains_project_id(self, tmp_path: Path) -> None:
        publish("Build the feature", "implement", "my-project", base=tmp_path)
        result = pickup(base=tmp_path)
        assert "my-project" in result

    def test_contains_objective(self, tmp_path: Path) -> None:
        publish("Build the feature", "implement", "my-project", base=tmp_path)
        result = pickup(base=tmp_path)
        assert "Build the feature" in result

    def test_contains_next_steps(self, tmp_path: Path) -> None:
        publish(
            "Fix the bug",
            "verify",
            "bugfix",
            next_steps=["Check logs", "Write regression test"],
            base=tmp_path,
        )
        result = pickup(base=tmp_path)
        assert "Check logs" in result
        assert "Write regression test" in result

    def test_project_id_override(self, tmp_path: Path) -> None:
        publish("X", "plan", "original-id", base=tmp_path)
        result = pickup(project_id="override-id", base=tmp_path)
        assert "override-id" in result

    def test_plan_phase_uses_planner(self, tmp_path: Path) -> None:
        publish("Plan the sprint", "plan", "sprint", base=tmp_path)
        result = pickup(base=tmp_path)
        assert "planner" in result

    def test_resume_phase_uses_resume_role(self, tmp_path: Path) -> None:
        publish("Continue work", "resume", "ongoing", base=tmp_path)
        result = pickup(base=tmp_path)
        assert "resume" in result


class TestRolePrompt:
    def test_basic_output(self, tmp_path: Path) -> None:
        result = role_prompt("my-project", "planner", phase="plan", base=tmp_path)
        assert "planner" in result
        assert "my-project" in result
        assert "think" in result

    def test_includes_agent(self, tmp_path: Path) -> None:
        result = role_prompt("proj", "planner", base=tmp_path)
        assert "claude" in result

    def test_includes_model_tier(self, tmp_path: Path) -> None:
        result = role_prompt("proj", "verifier", base=tmp_path)
        assert "medium" in result

    def test_includes_work_mode_description(self, tmp_path: Path) -> None:
        result = role_prompt("proj", "planner", phase="plan", base=tmp_path)
        assert "Token-sensitive" in result

    def test_includes_context_discipline(self, tmp_path: Path) -> None:
        result = role_prompt("proj", "planner", phase="plan", base=tmp_path)
        assert "Context discipline" in result

    def test_includes_tool_discipline(self, tmp_path: Path) -> None:
        result = role_prompt("proj", "planner", phase="plan", base=tmp_path)
        assert "Tool discipline" in result

    def test_includes_handoff_state_objective(self, tmp_path: Path) -> None:
        publish("Fix the login bug", "plan", "proj", base=tmp_path)
        result = role_prompt("proj", "planner", phase="plan", base=tmp_path)
        assert "Fix the login bug" in result

    def test_includes_handoff_next_steps(self, tmp_path: Path) -> None:
        publish(
            "Implement auth",
            "plan",
            "proj",
            next_steps=["Design tokens", "Review spec"],
            base=tmp_path,
        )
        result = role_prompt("proj", "planner", phase="plan", base=tmp_path)
        assert "Design tokens" in result
        assert "Review spec" in result

    def test_invalid_role_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            role_prompt("proj", "ghost", base=tmp_path)

    def test_no_state_still_works(self, tmp_path: Path) -> None:
        result = role_prompt("proj", "scaffold", base=tmp_path)
        assert "scaffold" in result
        assert "longContext" in result
