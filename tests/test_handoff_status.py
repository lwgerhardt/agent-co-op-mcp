"""Tests for handoff status reporting."""

from __future__ import annotations

from pathlib import Path

from agent_co_op.handoff import handoff_status, publish


class TestHandoffStatus:
    def test_empty_state(self, tmp_path: Path) -> None:
        status = handoff_status(base=tmp_path)
        assert status["has_state"] is False
        assert status["has_current_handoff"] is False
        assert status["state"] is None

    def test_after_publish(self, tmp_path: Path) -> None:
        publish("Build feature", "plan", "my-app", base=tmp_path)
        status = handoff_status(base=tmp_path)
        assert status["has_state"] is True
        assert status["has_current_handoff"] is True
        assert status["state"]["objective"] == "Build feature"
