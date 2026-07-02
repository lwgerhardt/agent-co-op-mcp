"""Tests for handoff update — patch state without full republish."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_co_op.handoff import (
    HandoffUpdateError,
    publish,
    read_current_handoff,
    read_state,
    update,
)
from agent_co_op.projects import pickup


class TestUpdate:
    def test_requires_existing_state(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No handoff state found"):
            update(next_steps=["Only step"], base=tmp_path)

    def test_requires_at_least_one_field(self, tmp_path: Path) -> None:
        publish("Build feature", "implement", "my-app", base=tmp_path)
        with pytest.raises(HandoffUpdateError, match="At least one update field"):
            update(base=tmp_path)

    def test_replace_next_steps(self, tmp_path: Path) -> None:
        publish(
            "Build feature",
            "implement",
            "my-app",
            next_steps=["Old step"],
            base=tmp_path,
        )
        state = update(next_steps=["New step", "Another step"], base=tmp_path)
        assert state["next_steps"] == ["New step", "Another step"]
        assert "updated_at" in state

    def test_append_next_steps(self, tmp_path: Path) -> None:
        publish(
            "Build feature",
            "implement",
            "my-app",
            next_steps=["First"],
            base=tmp_path,
        )
        state = update(append_next_steps=["Second"], base=tmp_path)
        assert state["next_steps"] == ["First", "Second"]

    def test_clear_next_steps(self, tmp_path: Path) -> None:
        publish(
            "Build feature",
            "implement",
            "my-app",
            next_steps=["First"],
            base=tmp_path,
        )
        state = update(clear_next_steps=True, base=tmp_path)
        assert state["next_steps"] == []

    def test_replace_objective(self, tmp_path: Path) -> None:
        publish("Old objective", "plan", "my-app", base=tmp_path)
        state = update(objective="New objective", base=tmp_path)
        assert state["objective"] == "New objective"

    def test_change_phase_recomputes_role(self, tmp_path: Path) -> None:
        publish("Implement auth", "implement", "my-app", base=tmp_path)
        state = update(phase="verify", base=tmp_path)
        assert state["phase"] == "verify"
        assert state["role"] == "verifier"
        assert state["work_mode"] == "background"

    def test_set_context(self, tmp_path: Path) -> None:
        publish("Build feature", "implement", "my-app", base=tmp_path)
        state = update(
            context="Decided to use JWT with refresh tokens.",
            base=tmp_path,
        )
        assert state["context"] == "Decided to use JWT with refresh tokens."
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "Decided to use JWT with refresh tokens." in content

    def test_clear_context(self, tmp_path: Path) -> None:
        publish(
            "Build feature",
            "implement",
            "my-app",
            context="Temporary note",
            base=tmp_path,
        )
        state = update(clear_context=True, base=tmp_path)
        assert "context" not in state

    def test_rejects_conflicting_next_step_flags(self, tmp_path: Path) -> None:
        publish("Build feature", "implement", "my-app", base=tmp_path)
        with pytest.raises(HandoffUpdateError, match="not both"):
            update(next_steps=["A"], append_next_steps=["B"], base=tmp_path)

    def test_rejects_empty_append_next_steps(self, tmp_path: Path) -> None:
        publish("Build feature", "implement", "my-app", base=tmp_path)
        with pytest.raises(HandoffUpdateError, match="at least one step"):
            update(append_next_steps=[], base=tmp_path)

    def test_pickup_includes_context(self, tmp_path: Path) -> None:
        publish("Build feature", "implement", "my-app", base=tmp_path)
        update(context="Use bcrypt for password hashing.", base=tmp_path)
        result = pickup(base=tmp_path)
        assert "Use bcrypt for password hashing." in result

    def test_preserves_published_at(self, tmp_path: Path) -> None:
        publish("Build feature", "implement", "my-app", base=tmp_path)
        before = read_state(tmp_path)
        assert before is not None
        state = update(next_steps=["Step"], base=tmp_path)
        assert state["published_at"] == before["published_at"]
        assert state["updated_at"] != before["published_at"]
