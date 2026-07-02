"""Tests for restoring archived handoff states."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_co_op.handoff import (
    handoff_history,
    list_history,
    publish,
    read_current_handoff,
    read_state,
    restore,
)
from agent_co_op.projects import pickup


class TestRestore:
    def test_restore_missing_entry_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No history entry found"):
            restore("missing-entry", base=tmp_path)

    def test_restore_rejects_unsafe_id(self, tmp_path: Path) -> None:
        publish("Plan auth", "plan", "my-app", base=tmp_path)
        publish("Implement auth", "implement", "my-app", base=tmp_path)
        with pytest.raises(FileNotFoundError):
            restore("../handoff-state", base=tmp_path)

    def test_restore_brings_back_archived_state(self, tmp_path: Path) -> None:
        publish("Plan auth", "plan", "my-app", base=tmp_path)
        publish("Implement auth", "implement", "my-app", base=tmp_path)

        entry_id = list_history(base=tmp_path)[-1]["id"]
        state = restore(entry_id, base=tmp_path)

        assert state["objective"] == "Plan auth"
        assert state["phase"] == "plan"
        assert state["role"] == "planner"
        assert state["work_mode"] == "think"
        assert state["restored_from_history_id"] == entry_id
        assert "restored_at" in state

        current = read_state(tmp_path)
        assert current is not None
        assert current["objective"] == "Plan auth"
        assert current["phase"] == "plan"

    def test_restore_archives_current_state_first(self, tmp_path: Path) -> None:
        publish("Plan auth", "plan", "my-app", base=tmp_path)
        publish("Implement auth", "implement", "my-app", base=tmp_path)

        plan_entry_id = list_history(base=tmp_path)[-1]["id"]
        restore(plan_entry_id, base=tmp_path)

        history = handoff_history(base=tmp_path)
        assert history["count"] == 2
        assert history["entries"][0]["objective"] == "Implement auth"
        assert history["entries"][1]["objective"] == "Plan auth"

    def test_restore_preserves_context_and_next_steps(self, tmp_path: Path) -> None:
        publish(
            "Plan auth",
            "plan",
            "my-app",
            next_steps=["Draft schema", "Review API"],
            context="Prefer JWT with refresh tokens.",
            base=tmp_path,
        )
        publish("Implement auth", "implement", "my-app", base=tmp_path)

        entry_id = list_history(base=tmp_path)[-1]["id"]
        state = restore(entry_id, base=tmp_path)

        assert state["next_steps"] == ["Draft schema", "Review API"]
        assert state["context"] == "Prefer JWT with refresh tokens."
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "Prefer JWT with refresh tokens." in content
        assert "Draft schema" in content

    def test_restore_pickup_uses_restored_state(self, tmp_path: Path) -> None:
        publish("Plan auth", "plan", "my-app", base=tmp_path)
        publish("Implement auth", "implement", "my-app", base=tmp_path)

        entry_id = list_history(base=tmp_path)[-1]["id"]
        restore(entry_id, base=tmp_path)

        result = pickup(base=tmp_path)
        assert "Plan auth" in result
        assert "planner" in result

    def test_restore_keeps_original_history_entry(self, tmp_path: Path) -> None:
        publish("Plan auth", "plan", "my-app", base=tmp_path)
        publish("Implement auth", "implement", "my-app", base=tmp_path)

        entry_id = list_history(base=tmp_path)[-1]["id"]
        restore(entry_id, base=tmp_path)

        ids = [entry["id"] for entry in list_history(base=tmp_path)]
        assert entry_id in ids

    def test_restore_without_current_state(self, tmp_path: Path) -> None:
        publish("Plan auth", "plan", "my-app", base=tmp_path)
        publish("Implement auth", "implement", "my-app", base=tmp_path)

        entry_id = list_history(base=tmp_path)[-1]["id"]
        from agent_co_op.handoff import clear

        clear(tmp_path)
        state = restore(entry_id, base=tmp_path)

        assert state["objective"] == "Plan auth"
        assert handoff_history(base=tmp_path)["count"] == 1

    def test_restore_invalid_history_state_raises(self, tmp_path: Path) -> None:
        history = tmp_path / ".agent-co-op" / "handoff-history"
        history.mkdir(parents=True)
        (history / "broken.json").write_text(
            '{"objective": "Missing phase"}', encoding="utf-8"
        )

        with pytest.raises(ValueError, match="missing required field"):
            restore("broken", base=tmp_path)
