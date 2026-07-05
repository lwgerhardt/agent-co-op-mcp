"""Normalize and render handoff context fields (v1 string and v2 object)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReadMapEntry:
    """A file reference in structured handoff context."""

    file: str
    lines: str = ""
    why: str = ""


@dataclass
class HandoffContextView:
    """Normalized view of handoff context for markdown rendering."""

    text: str = ""
    read_map: list[ReadMapEntry] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    manual_checks_pending: list[str] = field(default_factory=list)
    progress_summary: list[str] = field(default_factory=list)


def _nonempty_strings(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [item.strip() for item in items if isinstance(item, str) and item.strip()]


def _parse_read_map(raw: Any) -> list[ReadMapEntry]:
    if not isinstance(raw, list):
        return []
    entries: list[ReadMapEntry] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        file_path = entry.get("file")
        if not isinstance(file_path, str) or not file_path.strip():
            continue
        lines = entry.get("lines", "")
        why = entry.get("why", "")
        entries.append(
            ReadMapEntry(
                file=file_path.strip(),
                lines=lines.strip() if isinstance(lines, str) else "",
                why=why.strip() if isinstance(why, str) else "",
            )
        )
    return entries


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

    view.progress_summary = _nonempty_strings(raw.get("progress_summary"))
    view.blockers = _nonempty_strings(raw.get("blockers"))
    view.manual_checks_pending = _nonempty_strings(raw.get("manual_checks_pending"))
    view.read_map = _parse_read_map(raw.get("read_map"))
    return view


def _format_read_map_lines(entries: list[ReadMapEntry]) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        location = entry.file
        if entry.lines:
            location = f"{entry.file}:{entry.lines}"
        detail = f"{location} — {entry.why}" if entry.why else location
        lines.append(f"- {detail}")
    return lines


def format_context_sections(view: HandoffContextView) -> list[str]:
    """Return markdown lines for context sections."""
    lines: list[str] = []
    if view.text:
        lines += ["", "## Handoff context", view.text]

    list_sections = (
        ("Progress summary", view.progress_summary),
        ("Blockers", view.blockers),
        ("Manual checks pending", view.manual_checks_pending),
    )
    for title, items in list_sections:
        if not items:
            continue
        lines += ["", f"## {title}"]
        lines.extend(f"- {item}" for item in items)

    if view.read_map:
        lines += ["", "## Files to read (indexed)", *_format_read_map_lines(view.read_map)]
    return lines
