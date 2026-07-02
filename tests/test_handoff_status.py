"""Tests for handoff status reporting."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent_co_op.handoff import _handoff_dir, handoff_status, publish


class TestHandoffStatus:
    def test_empty_state(self, tmp_path: Path) -> None:
        status = handoff_status(base=tmp_path)
        assert status["active"] is False
        assert status["has_state"] is False
        assert status["has_current_handoff"] is False
        assert status["state"] is None
        assert "paths" in status

    def test_after_publish(self, tmp_path: Path) -> None:
        publish("Build feature", "plan", "my-app", base=tmp_path)
        status = handoff_status(base=tmp_path)
        assert status["active"] is True
        assert status["has_state"] is True
        assert status["has_current_handoff"] is True
        assert status["state"]["objective"] == "Build feature"
        assert status["phase"] == "plan"
        assert status["objective"] == "Build feature"
        assert "paths" in status
        assert status["paths"]["published_md"].endswith("CURRENT_HANDOFF.md")

    def test_stale_warning(self, tmp_path: Path) -> None:
        publish("Old work", "resume", "my-app", base=tmp_path)
        state_path = _handoff_dir(tmp_path) / "handoff-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        state["published_at"] = old
        state_path.write_text(json.dumps(state), encoding="utf-8")

        status = handoff_status(base=tmp_path)
        assert status["stale_warning"] == "handoff older than 7 days"
