"""Tests for v2 handoff markdown rendering."""

from __future__ import annotations

from pathlib import Path

from agent_co_op.handoff import publish, read_current_handoff


class TestHandoffV2Render:
    def test_read_map_blockers_in_markdown(self, tmp_path: Path) -> None:
        publish(
            "Build API",
            "implement",
            "my-app",
            context={
                "read_map": [
                    {"file": "src/api.py", "lines": "10-40", "why": "Routes"}
                ],
                "blockers": ["Waiting on credentials"],
                "manual_checks_pending": ["Verify logout"],
            },
            base=tmp_path,
        )
        content = read_current_handoff(tmp_path)
        assert content is not None
        assert "Files to read (indexed)" in content
        assert "src/api.py:10-40 — Routes" in content
        assert "Blockers" in content
        assert "Waiting on credentials" in content
        assert "Manual checks pending" in content
