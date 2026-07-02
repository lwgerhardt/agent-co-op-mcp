"""Normalize and render handoff context fields (v1 string and v2 object)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReadMapEntry:
    file: str
    lines: str = ""
    why: str = ""


@dataclass
class HandoffContextView:
    text: str = ""
    read_map: list[ReadMapEntry] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    manual_checks_pending: list[str] = field(default_factory=list)
    progress_summary: list[str] = field(default_factory=list)


def parse_context(state: dict[str, Any]) -> HandoffContextView:
    """Extract normalized context from handoff state."""
    view = HandoffContextView()
    raw = state.get("context")
    if isinstance(raw, str) and raw.strip():
        view.text = raw.strip()
        return view
    if not isinstance(raw, dict):
        return view

    notes = raw.get("notes")
    if isinstance(notes, str) and notes.strip():
        view.text = notes.strip()

    for item in raw.get("progress_summary", []):
        if isinstance(item, str) and item.strip():
            view.progress_summary.append(item.strip())

    for item in raw.get("blockers", []):
        if isinstance(item, str) and item.strip():
            view.blockers.append(item.strip())

    for item in raw.get("manual_checks_pending", []):
        if isinstance(item, str) and item.strip():
            view.manual_checks_pending.append(item.strip())

    read_map_raw = raw.get("read_map", [])
    if isinstance(read_map_raw, list):
        for entry in read_map_raw:
            if not isinstance(entry, dict):
                continue
            file_path = entry.get("file")
            if not isinstance(file_path, str) or not file_path.strip():
                continue
            lines = entry.get("lines", "")
            why = entry.get("why", "")
            view.read_map.append(
                ReadMapEntry(
                    file=file_path.strip(),
                    lines=lines.strip() if isinstance(lines, str) else "",
                    why=why.strip() if isinstance(why, str) else "",
                )
            )
    return view


def format_context_sections(view: HandoffContextView) -> list[str]:
    """Return markdown lines for context sections."""
    lines: list[str] = []
    if view.text:
        lines += ["", "## Handoff context", view.text]
    if view.progress_summary:
        lines += ["", "## Progress summary"]
        for item in view.progress_summary:
            lines.append(f"- {item}")
    if view.read_map:
        lines += ["", "## Files to read (indexed)"]
        for entry in view.read_map:
            location = entry.file
            if entry.lines:
                location = f"{entry.file}:{entry.lines}"
            detail = location
            if entry.why:
                detail = f"{location} — {entry.why}"
            lines.append(f"- {detail}")
    if view.blockers:
        lines += ["", "## Blockers"]
        for item in view.blockers:
            lines.append(f"- {item}")
    if view.manual_checks_pending:
        lines += ["", "## Manual checks pending"]
        for item in view.manual_checks_pending:
            lines.append(f"- {item}")
    return lines
