"""Tests for handoff module — publish, clear, read_state."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_co_op.handoff import (
    clear,
    publish,
    read_current_handoff,
    read_state,
)


class TestPublish:
    def test_creates_state_file(self, tmp_path: Path) -> None:
        publish("Build the API", "implement", "my-project", base=tmp_path)
        state_file = tmp_path / ".agent-co-op" / "handoff-state.json"
        assert state_file.exists()

    def test_creates_handoff_md(self, tmp_path: Path) -> None:
        publish("Build the API", "implement", "my-project", base=tmp_path)
        assert (tmp_path / ".agent-co-op" / "handoff.md").exists()

    def test_creates_current_handoff_md(self, tmp_path: Path) -> None:
        publish("Build the API", "implement", "my-project", base=tmp_path)
        assert (tmp_path / ".agent-co-op" / "CURRENT_HANDOFF.md").exists()

    def test_state_contents(self, tmp_path: Path) -> None:
        publish(
            "Build the API",
            "implement",
            "my-project",
            next_steps=["Write tests", "Deploy"],
            base=tmp_path,
        )
        state = read_state(tmp_path)
        assert state is not None
        assert state["objective"] == "Build the API"
        assert state["phase"] == "implement"
        assert state["project_id"] == "my-project"
        assert state["role"] == "verifier"
        assert state["work_mode"] == "background"
        assert state["next_steps"] == ["Write tests", "Deploy"]
        assert "published_at" in state

    def test_plan_phase_sets_planner_role(self, tmp_path: Path) -> None:
        publish("Design the schema", "plan", "schema-proj", base=tmp_path)
        state = read_state(tmp_path)
        assert state is not None
        assert state["role"] == "planner"
        assert state["work_mode"] == "think"

    def test_invalid_phase_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            publish("Test", "deploy", "proj", base=tmp_path)

    def test_no_next_steps(self, tmp_path: Path) -> None:
        publish("Objective", "verify", "proj", base=tmp_path)
        state = read_state(tmp_path)
        assert state is not None
        assert state["next_steps"] == []

    def test_creates_dir_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "subdir"
        publish("X", "plan", "p", base=nested)
        assert (nested / ".agent-co-op" / "handoff-state.json").exists()

    def test_handoff_md_contains_objective(self, tmp_path: Path) -> None:
        publish("Fix the login bug", "verify", "bugfix", base=tmp_path)
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "Fix the login bug" in content


class TestClear:
    def test_clear_removes_files(self, tmp_path: Path) -> None:
        publish("Test", "plan", "proj", base=tmp_path)
        clear(tmp_path)
        assert read_state(tmp_path) is None
        assert read_current_handoff(tmp_path) is None
        assert not (tmp_path / ".agent-co-op" / "handoff.md").exists()

    def test_clear_is_idempotent(self, tmp_path: Path) -> None:
        clear(tmp_path)
        clear(tmp_path)


class TestReadState:
    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert read_state(tmp_path) is None

    def test_returns_dict_when_present(self, tmp_path: Path) -> None:
        publish("X", "plan", "p", base=tmp_path)
        result = read_state(tmp_path)
        assert isinstance(result, dict)


class TestReadCurrentHandoff:
    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert read_current_handoff(tmp_path) is None

    def test_returns_string_when_present(self, tmp_path: Path) -> None:
        publish("X", "plan", "p", base=tmp_path)
        result = read_current_handoff(tmp_path)
        assert isinstance(result, str)
        assert len(result) > 0
