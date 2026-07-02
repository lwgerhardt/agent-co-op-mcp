"""Capture, publish, and clear handoff state files in .agent-co-op/."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HANDOFF_DIRNAME = ".agent-co-op"
_HISTORY_DIRNAME = "handoff-history"
_SAFE_ENTRY_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


class HandoffUpdateError(ValueError):
    """Raised when a handoff update request is invalid."""


def _handoff_dir(base: Path | None = None) -> Path:
    return (base or Path.cwd()) / _HANDOFF_DIRNAME


def _write_handoff_files(state: dict[str, Any], base: Path | None = None) -> None:
    from .routing import resolve_routing

    routing = resolve_routing(
        state["role"],
        phase=state["phase"],
        project_id=state["project_id"],
        base=base,
    )
    d = _handoff_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    (d / "handoff-state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    summary_md = _render_handoff_md(state, routing)
    (d / "handoff.md").write_text(summary_md, encoding="utf-8")
    (d / "CURRENT_HANDOFF.md").write_text(summary_md, encoding="utf-8")


def _history_dir(base: Path | None = None) -> Path:
    return _handoff_dir(base) / _HISTORY_DIRNAME


def _safe_history_stem(published_at: str, phase: str) -> str:
    """Build a filename-safe stem from an ISO timestamp and phase."""
    dt = datetime.fromisoformat(published_at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    stamp = dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_phase = re.sub(r"[^a-zA-Z0-9_-]+", "-", phase).strip("-") or "handoff"
    return f"{stamp}_{safe_phase}"


def _archive_current_state(base: Path | None = None) -> str | None:
    """Archive the current handoff files before they are overwritten.

    Returns the history entry id when an archive was written, else None.
    """
    state = read_state(base)
    if state is None:
        return None

    published_at = state.get("published_at")
    phase = state.get("phase", "handoff")
    if not isinstance(published_at, str) or not published_at:
        published_at = datetime.now(timezone.utc).isoformat()

    history = _history_dir(base)
    history.mkdir(parents=True, exist_ok=True)

    base_stem = _safe_history_stem(published_at, str(phase))
    stem = base_stem
    suffix = 1
    while (history / f"{stem}.json").exists():
        stem = f"{base_stem}-{suffix}"
        suffix += 1

    (history / f"{stem}.json").write_text(
        json.dumps(
            {
                **state,
                "archived_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    md_path = _handoff_dir(base) / "handoff.md"
    if md_path.exists():
        (history / f"{stem}.md").write_text(
            md_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    return stem


def list_history(
    base: Path | None = None, limit: int | None = None
) -> list[dict[str, Any]]:
    """Return archived handoff entries, newest first."""
    history = _history_dir(base)
    if not history.exists():
        return []

    items: list[tuple[str, dict[str, Any]]] = []
    for json_path in history.glob("*.json"):
        state = json.loads(json_path.read_text(encoding="utf-8"))
        items.append((json_path.stem, state))
    items.sort(
        key=lambda item: item[1].get("archived_at", item[1].get("published_at", "")),
        reverse=True,
    )

    entries: list[dict[str, Any]] = []
    for stem, state in items:
        md_path = history / f"{stem}.md"
        entries.append(
            {
                "id": stem,
                "published_at": state.get("published_at"),
                "phase": state.get("phase"),
                "project_id": state.get("project_id"),
                "objective": state.get("objective"),
                "role": state.get("role"),
                "has_markdown": md_path.exists(),
            }
        )
        if limit is not None and len(entries) >= limit:
            break
    return entries


def read_history_entry(
    entry_id: str, base: Path | None = None
) -> dict[str, Any] | None:
    """Return a single archived handoff entry by id."""
    if not _SAFE_ENTRY_ID.fullmatch(entry_id):
        return None

    history = _history_dir(base)
    json_path = (history / f"{entry_id}.json").resolve()
    if not json_path.is_relative_to(history.resolve()):
        return None
    if not json_path.exists():
        return None

    state = json.loads(json_path.read_text(encoding="utf-8"))
    md_path = history / f"{entry_id}.md"
    markdown = md_path.read_text(encoding="utf-8") if md_path.exists() else None
    return {"id": entry_id, "state": state, "markdown": markdown}


def handoff_history(
    base: Path | None = None, limit: int | None = None
) -> dict[str, Any]:
    """Return archived handoff metadata for CLI/MCP consumers."""
    entries = list_history(base, limit=limit)
    return {"count": len(entries), "entries": entries}


def restore(entry_id: str, base: Path | None = None) -> dict[str, Any]:
    """Restore a prior handoff state from history as the current handoff.

    Archives the current state first when one exists. The history entry
    itself is left in place. Raises FileNotFoundError when the entry is
    missing and ValueError when the archived state is invalid.
    """
    from .routing import phase_to_role, resolve_routing

    entry = read_history_entry(entry_id, base=base)
    if entry is None:
        raise FileNotFoundError(
            f"No history entry found for {entry_id!r}. "
            "Run 'agent-co-op handoff history' to list ids."
        )

    raw_state = entry["state"]
    for field in ("phase", "objective", "project_id"):
        value = raw_state.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"History entry {entry_id!r} is missing required field {field!r}."
            )

    _archive_current_state(base)

    phase = raw_state["phase"]
    project_id = raw_state["project_id"]
    role = phase_to_role(phase)
    routing = resolve_routing(role, phase=phase, project_id=project_id, base=base)

    next_steps_raw = raw_state.get("next_steps", [])
    next_steps: list[str] = (
        list(next_steps_raw) if isinstance(next_steps_raw, list) else []
    )

    now = datetime.now(timezone.utc).isoformat()
    published_at = raw_state.get("published_at")
    if not isinstance(published_at, str) or not published_at:
        published_at = now

    state: dict[str, Any] = {
        "phase": phase,
        "objective": raw_state["objective"],
        "project_id": project_id,
        "role": role,
        "work_mode": routing["work_mode"],
        "next_steps": next_steps,
        "published_at": published_at,
        "updated_at": now,
        "restored_at": now,
        "restored_from_history_id": entry_id,
    }

    context = raw_state.get("context")
    if isinstance(context, str) and context.strip():
        state["context"] = context.strip()

    _write_handoff_files(state, base=base)
    return state


def publish(
    objective: str,
    phase: str,
    project_id: str,
    next_steps: list[str] | None = None,
    context: str | None = None,
    base: Path | None = None,
) -> None:
    """Write handoff-state.json, handoff.md, and CURRENT_HANDOFF.md.

    Files are written under <base>/.agent-co-op/ (defaults to cwd).
    Raises ValueError for unknown phases.
    """
    from .routing import phase_to_role, resolve_routing

    role = phase_to_role(phase)
    routing = resolve_routing(role, phase=phase, project_id=project_id, base=base)
    steps: list[str] = next_steps or []
    now = datetime.now(timezone.utc).isoformat()

    _archive_current_state(base)

    state: dict[str, Any] = {
        "phase": phase,
        "objective": objective,
        "project_id": project_id,
        "role": role,
        "work_mode": routing["work_mode"],
        "next_steps": steps,
        "published_at": now,
        "updated_at": now,
    }
    if context:
        state["context"] = context

    _write_handoff_files(state, base=base)


def update(
    *,
    objective: str | None = None,
    phase: str | None = None,
    next_steps: list[str] | None = None,
    append_next_steps: list[str] | None = None,
    context: str | None = None,
    clear_context: bool = False,
    clear_next_steps: bool = False,
    base: Path | None = None,
) -> dict[str, Any]:
    """Patch the current handoff state without a full republish.

    Only supplied fields are changed. ``next_steps`` replaces the full list;
    ``append_next_steps`` adds to the existing list. Raises FileNotFoundError
    when no handoff exists and HandoffUpdateError for invalid requests.
    """
    from .routing import phase_to_role, resolve_routing

    if next_steps is not None and append_next_steps is not None:
        raise HandoffUpdateError(
            "Specify either next_steps or append_next_steps, not both."
        )
    if clear_next_steps and (
        next_steps is not None or append_next_steps is not None
    ):
        raise HandoffUpdateError(
            "clear_next_steps cannot be combined with next_steps or append_next_steps."
        )
    if context is not None and clear_context:
        raise HandoffUpdateError("Specify either context or clear_context, not both.")
    if append_next_steps is not None and not append_next_steps:
        raise HandoffUpdateError("append_next_steps requires at least one step.")

    has_change = any(
        value is not None
        for value in (
            objective,
            phase,
            next_steps,
            append_next_steps,
            context,
        )
    ) or clear_context or clear_next_steps
    if not has_change:
        raise HandoffUpdateError(
            "At least one update field is required "
            "(objective, phase, next_steps, append_next_steps, context, "
            "clear_context, or clear_next_steps)."
        )

    state = read_state(base)
    if state is None:
        raise FileNotFoundError(
            "No handoff state found. Run 'agent-co-op handoff publish' first."
        )

    if objective is not None:
        state["objective"] = objective

    if phase is not None:
        role = phase_to_role(phase)
        routing = resolve_routing(
            role,
            phase=phase,
            project_id=state["project_id"],
            base=base,
        )
        state["phase"] = phase
        state["role"] = role
        state["work_mode"] = routing["work_mode"]

    if clear_next_steps:
        state["next_steps"] = []
    elif next_steps is not None:
        state["next_steps"] = next_steps
    elif append_next_steps is not None:
        existing: list[str] = list(state.get("next_steps", []))
        existing.extend(append_next_steps)
        state["next_steps"] = existing

    if clear_context:
        state.pop("context", None)
    elif context is not None:
        if context.strip():
            state["context"] = context
        else:
            state.pop("context", None)

    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_handoff_files(state, base=base)
    return state


def _render_handoff_md(state: dict[str, Any], routing: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# Handoff — {state['project_id']} / {state['phase']}",
        "",
        f"**Objective:** {state['objective']}",
        f"**Phase:** {state['phase']}",
        f"**Role:** {state['role']}",
        f"**Work mode:** {state['work_mode']} — {routing['work_mode_description']}",
    ]
    handoff_context = state.get("context")
    if isinstance(handoff_context, str) and handoff_context.strip():
        lines += ["", "## Handoff context", handoff_context.strip()]
    lines += ["", "## Context discipline"]
    for bullet in routing["context_discipline"]:
        lines.append(f"- {bullet}")
    lines += ["", "## Tool discipline"]
    for bullet in routing["tool_discipline"]:
        lines.append(f"- {bullet}")
    if state["next_steps"]:
        lines += ["", "## Next steps"]
        for step in state["next_steps"]:
            lines.append(f"- {step}")
    lines += [
        "",
        f"*Published at {state['published_at']}*",
    ]
    updated_at = state.get("updated_at")
    if updated_at and updated_at != state.get("published_at"):
        lines.append(f"*Updated at {updated_at}*")
    restored_at = state.get("restored_at")
    if isinstance(restored_at, str) and restored_at:
        lines.append(f"*Restored at {restored_at}*")
    return "\n".join(lines) + "\n"


def clear(base: Path | None = None) -> None:
    """Remove all handoff files from .agent-co-op/."""
    d = _handoff_dir(base)
    for name in ("handoff-state.json", "handoff.md", "CURRENT_HANDOFF.md"):
        p = d / name
        if p.exists():
            p.unlink()


def handoff_status(base: Path | None = None) -> dict[str, Any]:
    """Return current handoff state plus whether a pickup prompt is available."""
    state = read_state(base)
    current = read_current_handoff(base)
    return {
        "has_state": state is not None,
        "has_current_handoff": current is not None,
        "state": state,
    }


def read_state(base: Path | None = None) -> dict[str, Any] | None:
    """Return parsed handoff-state.json, or None if the file is missing."""
    p = _handoff_dir(base) / "handoff-state.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def read_current_handoff(base: Path | None = None) -> str | None:
    """Return the contents of CURRENT_HANDOFF.md, or None if missing."""
    p = _handoff_dir(base) / "CURRENT_HANDOFF.md"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")
