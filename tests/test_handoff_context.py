"""Tests for handoff context parsing and rendering."""

from __future__ import annotations

from agent_co_op.handoff_context import (
    HandoffContextView,
    ReadMapEntry,
    format_context_sections,
    parse_context,
)


class TestHandoffContext:
    def test_parse_string_context(self) -> None:
        view = parse_context({"context": "Decisions from planning"})
        assert view.text == "Decisions from planning"
        assert view.read_map == []

    def test_parse_v2_context(self) -> None:
        view = parse_context(
            {
                "context": {
                    "read_map": [
                        {"file": "src/app.py", "lines": "1-20", "why": "Entry point"}
                    ],
                    "blockers": ["Needs API key"],
                    "manual_checks_pending": ["Check logout"],
                }
            }
        )
        assert len(view.read_map) == 1
        assert view.read_map[0].file == "src/app.py"
        assert view.blockers == ["Needs API key"]
        assert view.manual_checks_pending == ["Check logout"]

    def test_format_context_sections(self) -> None:
        view = HandoffContextView(
            read_map=[ReadMapEntry(file="a.py", lines="1-5", why="core")],
            blockers=["blocked"],
            manual_checks_pending=["manual"],
        )
        rendered = "\n".join(format_context_sections(view))
        assert "Files to read (indexed)" in rendered
        assert "a.py:1-5 — core" in rendered
        assert "Blockers" in rendered
        assert "Manual checks pending" in rendered
