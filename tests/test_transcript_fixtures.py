"""Validate synthetic transcript fixtures used for future capture parsing."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "transcripts"
FIXTURE_FILES = (
    "cursor-session.example.jsonl",
    "claude-session.example.jsonl",
)


def _load_entries(path: Path) -> list[dict]:
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entries.append(json.loads(line))
    return entries


def _tool_uses(entry: dict) -> list[dict]:
    message = entry.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict) and block.get("name")]


class TestTranscriptFixtures:
    def test_fixture_files_exist(self) -> None:
        for name in FIXTURE_FILES:
            assert (FIXTURES_DIR / name).is_file()

    def test_each_line_is_valid_json_object(self) -> None:
        for name in FIXTURE_FILES:
            entries = _load_entries(FIXTURES_DIR / name)
            assert entries, f"{name} should contain at least one entry"
            for entry in entries:
                assert isinstance(entry, dict)

    def test_cursor_fixture_has_expected_tool_names(self) -> None:
        entries = _load_entries(FIXTURES_DIR / "cursor-session.example.jsonl")
        tool_names = {
            block["name"]
            for entry in entries
            for block in _tool_uses(entry)
            if block.get("name")
        }
        assert {"TodoWrite", "StrReplace", "Write"}.issubset(tool_names)

    def test_claude_fixture_has_expected_tool_names(self) -> None:
        entries = _load_entries(FIXTURES_DIR / "claude-session.example.jsonl")
        tool_names = {
            block["name"]
            for entry in entries
            for block in _tool_uses(entry)
            if block.get("name")
        }
        assert {"TodoWrite", "Edit", "Write"}.issubset(tool_names)

    def test_cursor_fixture_ends_with_user_handoff_prompt(self) -> None:
        entries = _load_entries(FIXTURES_DIR / "cursor-session.example.jsonl")
        last = entries[-1]
        assert last.get("role") == "user"
        message = last.get("message", {})
        content = message.get("content", []) if isinstance(message, dict) else []
        text = " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
        assert "Publish handoff for verifier" in text
