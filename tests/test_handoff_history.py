"""Tests for archived handoff history."""

from __future__ import annotations

import json
from pathlib import Path

from agent_co_op.handoff import (
    _safe_history_stem,
    handoff_history,
    list_history,
    publish,
    read_history_entry,
    read_state,
)


class TestHandoffHistoryArchive:
    def test_first_publish_creates_no_history(self, tmp_path: Path) -> None:
        publish("Plan auth", "plan", "my-app", base=tmp_path)
        assert handoff_history(base=tmp_path)["count"] == 0

    def test_second_publish_archives_previous_state(self, tmp_path: Path) -> None:
        publish("Plan auth", "plan", "my-app", base=tmp_path)
        publish("Implement auth", "implement", "my-app", base=tmp_path)

        history = handoff_history(base=tmp_path)
        assert history["count"] == 1
        entry = history["entries"][0]
        assert entry["phase"] == "plan"
        assert entry["objective"] == "Plan auth"
        assert entry["project_id"] == "my-app"
        assert entry["has_markdown"] is True

        current = read_state(tmp_path)
        assert current is not None
        assert current["phase"] == "implement"
        assert current["objective"] == "Implement auth"

    def test_multiple_publishes_keep_newest_first(self, tmp_path: Path) -> None:
        publish("Step 1", "plan", "my-app", base=tmp_path)
        publish("Step 2", "implement", "my-app", base=tmp_path)
        publish("Step 3", "verify", "my-app", base=tmp_path)

        entries = list_history(base=tmp_path)
        assert [entry["objective"] for entry in entries] == [
            "Step 2",
            "Step 1",
        ]

    def test_limit_returns_recent_entries(self, tmp_path: Path) -> None:
        publish("Step 1", "plan", "my-app", base=tmp_path)
        publish("Step 2", "implement", "my-app", base=tmp_path)
        publish("Step 3", "verify", "my-app", base=tmp_path)

        entries = list_history(base=tmp_path, limit=1)
        assert len(entries) == 1
        assert entries[0]["objective"] == "Step 2"

    def test_read_history_entry_returns_state_and_markdown(
        self, tmp_path: Path
    ) -> None:
        publish("Plan auth", "plan", "my-app", base=tmp_path)
        publish("Implement auth", "implement", "my-app", base=tmp_path)

        entry_id = list_history(base=tmp_path)[0]["id"]
        entry = read_history_entry(entry_id, base=tmp_path)
        assert entry is not None
        assert entry["state"]["objective"] == "Plan auth"
        assert entry["markdown"] is not None
        assert "Plan auth" in entry["markdown"]

    def test_read_history_entry_missing_returns_none(self, tmp_path: Path) -> None:
        assert read_history_entry("missing-entry", base=tmp_path) is None

    def test_read_history_entry_rejects_unsafe_id(self, tmp_path: Path) -> None:
        publish("Plan auth", "plan", "my-app", base=tmp_path)
        publish("Implement auth", "implement", "my-app", base=tmp_path)
        assert read_history_entry("../handoff-state", base=tmp_path) is None

    def test_collision_uses_sequential_suffix(self, tmp_path: Path) -> None:
        publish("First", "plan", "my-app", base=tmp_path)
        state = read_state(tmp_path)
        assert state is not None
        stem = _safe_history_stem(state["published_at"], "plan")

        history = tmp_path / ".agent-co-op" / "handoff-history"
        history.mkdir(parents=True, exist_ok=True)
        (history / f"{stem}.json").write_text(
            json.dumps({**state, "objective": "Collision"}), encoding="utf-8"
        )
        (tmp_path / ".agent-co-op" / "handoff-state.json").write_text(
            json.dumps({**state, "objective": "To archive"}), encoding="utf-8"
        )

        publish("Second", "plan", "my-app", base=tmp_path)

        entry_ids = [entry["id"] for entry in list_history(base=tmp_path)]
        assert f"{stem}-1" in entry_ids

    def test_skips_corrupt_history_entries(self, tmp_path: Path, capsys) -> None:
        publish("Good entry", "plan", "my-app", base=tmp_path)
        publish("Next entry", "implement", "my-app", base=tmp_path)

        history = tmp_path / ".agent-co-op" / "handoff-history"
        (history / "corrupt-entry.json").write_text("{bad json", encoding="utf-8")

        entries = list_history(base=tmp_path)
        assert len(entries) == 1
        assert entries[0]["objective"] == "Good entry"
        captured = capsys.readouterr()
        assert "Warning: skipping corrupt history entry corrupt-entry" in captured.err