"""Capture, publish, and clear handoff state files in .agent-co-op/."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
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
    """Write handoff JSON and markdown via temp files, then atomic replace."""
    from .routing import resolve_routing

    routing = resolve_routing(
        state["role"],
        phase=state["phase"],
        project_id=state["project_id"],
        base=base,
    )
    d = _handoff_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    summary_md = _render_handoff_md(state, routing)

    tmp_state = ""
    tmp_handoff_md = ""
    tmp_current_md = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=d,
            prefix=".tmp-",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            json.dump(state, tmp, indent=2)
            tmp_state = tmp.name

        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=d,
            prefix=".tmp-",
            suffix=".md",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(summary_md)
            tmp_handoff_md = tmp.name

        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=d,
            prefix=".tmp-",
            suffix=".md",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(summary_md)
            tmp_current_md = tmp.name

        os.replace(tmp_state, d / "handoff-state.json")
        os.replace(tmp_handoff_md, d / "handoff.md")
        os.replace(tmp_current_md, d / "CURRENT_HANDOFF.md")
    except Exception:
        for tmp_path in (tmp_state, tmp_handoff_md, tmp_current_md):
            if tmp_path:
                try:
                    Path(tmp_path).unlink()
                except OSError:
                    pass
        raise


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
        try:
            state = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(
                f"Warning: skipping corrupt history entry {json_path.stem}: {exc}",
                file=sys.stderr,
            )
            continue
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

    try:
        state = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Corrupted history entry at {json_path}: {exc}."
        ) from exc
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

    git_snapshot = _capture_git_snapshot(base)
    if git_snapshot is not None:
        state["git"] = git_snapshot

    _write_handoff_files(state, base=base)
    return state


def publish(
    objective: str,
    phase: str,
    project_id: str,
    next_steps: list[str] | None = None,
    context: str | dict[str, Any] | None = None,
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

    git_snapshot = _capture_git_snapshot(base)
    if git_snapshot is not None:
        state["git"] = git_snapshot

    _warn_state_schema(state)
    _write_handoff_files(state, base=base)


def _update_conflict_message(
    *,
    next_steps: list[str] | None,
    append_next_steps: list[str] | None,
    context: str | dict[str, Any] | None,
    clear_context: bool,
    clear_next_steps: bool,
) -> str | None:
    if next_steps is not None and append_next_steps is not None:
        return "Specify either next_steps or append_next_steps, not both."
    if clear_next_steps and (
        next_steps is not None or append_next_steps is not None
    ):
        return (
            "clear_next_steps cannot be combined with next_steps or "
            "append_next_steps."
        )
    if context is not None and clear_context:
        return "Specify either context or clear_context, not both."
    if append_next_steps is not None and not append_next_steps:
        return "append_next_steps requires at least one step."
    return None


def _has_update_change(
    *,
    objective: str | None,
    phase: str | None,
    next_steps: list[str] | None,
    append_next_steps: list[str] | None,
    context: str | dict[str, Any] | None,
    clear_context: bool,
    clear_next_steps: bool,
) -> bool:
    return any(
        value is not None
        for value in (
            objective,
            phase,
            next_steps,
            append_next_steps,
            context,
        )
    ) or clear_context or clear_next_steps


def _validate_update_args(
    *,
    objective: str | None,
    phase: str | None,
    next_steps: list[str] | None,
    append_next_steps: list[str] | None,
    context: str | dict[str, Any] | None,
    clear_context: bool,
    clear_next_steps: bool,
) -> None:
    conflict = _update_conflict_message(
        next_steps=next_steps,
        append_next_steps=append_next_steps,
        context=context,
        clear_context=clear_context,
        clear_next_steps=clear_next_steps,
    )
    if conflict:
        raise HandoffUpdateError(conflict)
    if not _has_update_change(
        objective=objective,
        phase=phase,
        next_steps=next_steps,
        append_next_steps=append_next_steps,
        context=context,
        clear_context=clear_context,
        clear_next_steps=clear_next_steps,
    ):
        raise HandoffUpdateError(
            "At least one update field is required "
            "(objective, phase, next_steps, append_next_steps, context, "
            "clear_context, or clear_next_steps)."
        )


def _apply_phase_update(
    state: dict[str, Any], phase: str, base: Path | None
) -> None:
    from .routing import phase_to_role, resolve_routing

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


def _apply_next_steps_update(
    state: dict[str, Any],
    *,
    next_steps: list[str] | None,
    append_next_steps: list[str] | None,
    clear_next_steps: bool,
) -> None:
    if clear_next_steps:
        state["next_steps"] = []
    elif next_steps is not None:
        state["next_steps"] = next_steps
    elif append_next_steps is not None:
        existing: list[str] = list(state.get("next_steps", []))
        existing.extend(append_next_steps)
        state["next_steps"] = existing


def _apply_context_update(
    state: dict[str, Any],
    context: str | dict[str, Any] | None,
    clear_context: bool,
) -> None:
    if clear_context:
        state.pop("context", None)
        return
    if context is None:
        return
    if isinstance(context, dict):
        state["context"] = context
    elif context.strip():
        state["context"] = context
    else:
        state.pop("context", None)


def _apply_update_fields(
    state: dict[str, Any],
    *,
    objective: str | None,
    phase: str | None,
    next_steps: list[str] | None,
    append_next_steps: list[str] | None,
    context: str | dict[str, Any] | None,
    clear_context: bool,
    clear_next_steps: bool,
    base: Path | None,
) -> None:
    if objective is not None:
        state["objective"] = objective
    if phase is not None:
        _apply_phase_update(state, phase, base)
    _apply_next_steps_update(
        state,
        next_steps=next_steps,
        append_next_steps=append_next_steps,
        clear_next_steps=clear_next_steps,
    )
    _apply_context_update(state, context, clear_context)


def _finalize_handoff_state(state: dict[str, Any], base: Path | None) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    git_snapshot = _capture_git_snapshot(base)
    if git_snapshot is not None:
        state["git"] = git_snapshot
    _warn_state_schema(state)
    _write_handoff_files(state, base=base)


def update(
    *,
    objective: str | None = None,
    phase: str | None = None,
    next_steps: list[str] | None = None,
    append_next_steps: list[str] | None = None,
    context: str | dict[str, Any] | None = None,
    clear_context: bool = False,
    clear_next_steps: bool = False,
    base: Path | None = None,
) -> dict[str, Any]:
    """Patch the current handoff state without a full republish.

    Only supplied fields are changed. ``next_steps`` replaces the full list;
    ``append_next_steps`` adds to the existing list. Raises FileNotFoundError
    when no handoff exists and HandoffUpdateError for invalid requests.
    """
    _validate_update_args(
        objective=objective,
        phase=phase,
        next_steps=next_steps,
        append_next_steps=append_next_steps,
        context=context,
        clear_context=clear_context,
        clear_next_steps=clear_next_steps,
    )

    state = read_state(base)
    if state is None:
        raise FileNotFoundError(
            "No handoff state found. Run 'agent-co-op handoff publish' first."
        )

    _apply_update_fields(
        state,
        objective=objective,
        phase=phase,
        next_steps=next_steps,
        append_next_steps=append_next_steps,
        context=context,
        clear_context=clear_context,
        clear_next_steps=clear_next_steps,
        base=base,
    )
    _finalize_handoff_state(state, base)
    return state


def _append_rendered_context(lines: list[str], state: dict[str, Any]) -> None:
    handoff_context = state.get("context")
    if isinstance(handoff_context, str) and handoff_context.strip():
        lines += ["", "## Handoff context", handoff_context.strip()]
    elif isinstance(handoff_context, dict):
        from .handoff_context import format_context_sections, parse_context

        lines += format_context_sections(parse_context(state))


def _append_rendered_timestamps(lines: list[str], state: dict[str, Any]) -> None:
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


def _render_handoff_md(state: dict[str, Any], routing: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# Handoff — {state['project_id']} / {state['phase']}",
        "",
        f"**Objective:** {state['objective']}",
        f"**Phase:** {state['phase']}",
        f"**Role:** {state['role']}",
        f"**Work mode:** {state['work_mode']} — {routing['work_mode_description']}",
    ]
    _append_rendered_context(lines, state)
    git_block = state.get("git")
    if isinstance(git_block, dict):
        lines += _format_git_lines(git_block)
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
    _append_rendered_timestamps(lines, state)
    return "\n".join(lines) + "\n"


def clear(base: Path | None = None) -> None:
    """Remove all handoff files from .agent-co-op/."""
    d = _handoff_dir(base)
    for name in ("handoff-state.json", "handoff.md", "CURRENT_HANDOFF.md"):
        p = d / name
        if p.exists():
            p.unlink()


def _handoff_paths(base: Path | None = None) -> dict[str, str]:
    from .verification import queue_path, report_json_path, report_md_path

    d = _handoff_dir(base)
    return {
        "state_json": str(d / "handoff-state.json"),
        "handoff_md": str(d / "handoff.md"),
        "published_md": str(d / "CURRENT_HANDOFF.md"),
        "history_dir": str(_history_dir(base)),
        "verification_queue": str(queue_path(base)),
        "verification_report_md": str(report_md_path(base)),
        "verification_report_json": str(report_json_path(base)),
    }


def _warn_state_schema(state: dict[str, Any]) -> None:
    from .handoff_state import validate_handoff_state

    for warning in validate_handoff_state(state):
        print(f"Warning: handoff state schema: {warning}", file=sys.stderr)


def _verification_warning(
    state: dict[str, Any], base: Path | None = None
) -> str | None:
    if state.get("phase") != "implement":
        return None
    next_steps = state.get("next_steps", [])
    if isinstance(next_steps, list) and next_steps:
        return None
    from .verification import queue_exists

    if queue_exists(base):
        return None
    return (
        "implement phase has no next_steps and no verification queue; "
        "add verification steps before handoff to verifier"
    )


def _capture_git_snapshot(base: Path | None = None) -> dict[str, Any] | None:
    from .git_snapshot import capture_git_snapshot

    return capture_git_snapshot(base)


def _format_git_lines(git: dict[str, Any]) -> list[str]:
    from .git_snapshot import format_git_section_lines

    return format_git_section_lines(git)


def _stale_warning(
    published_at: str | None, days: int = 7
) -> str | None:
    if not published_at:
        return None
    try:
        dt = datetime.fromisoformat(published_at)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
    if age.days >= days:
        return f"handoff older than {days} days"
    return None


def _branch_mismatch_warning(
    state: dict[str, Any], base: Path | None = None
) -> str | None:
    from .git_snapshot import current_branch

    git_block = state.get("git")
    if not isinstance(git_block, dict):
        return None
    stored_branch = git_block.get("branch")
    if not isinstance(stored_branch, str) or not stored_branch:
        return None
    current = current_branch(base)
    if not current or current == stored_branch:
        return None
    return (
        f"Handoff was published on branch {stored_branch!r} but current branch is "
        f"{current!r}. Run: git checkout {stored_branch}"
    )


def handoff_status(base: Path | None = None) -> dict[str, Any]:
    """Return current handoff state plus whether a pickup prompt is available."""
    state = read_state(base)
    current = read_current_handoff(base)
    active = state is not None and current is not None
    result: dict[str, Any] = {
        "active": active,
        "has_state": state is not None,
        "has_current_handoff": current is not None,
        "state": state,
        "paths": _handoff_paths(base),
    }
    if state is not None:
        published_at = state.get("published_at")
        if isinstance(published_at, str):
            result["created_at"] = published_at
            stale = _stale_warning(published_at)
            if stale:
                result["stale_warning"] = stale
        branch_warning = _branch_mismatch_warning(state, base)
        if branch_warning:
            result["branch_mismatch_warning"] = branch_warning
        verification_warning = _verification_warning(state, base)
        if verification_warning:
            result["verification_warning"] = verification_warning
        for key in ("phase", "objective", "project_id", "role"):
            if key in state:
                result[key] = state[key]
    return result


def read_state(base: Path | None = None) -> dict[str, Any] | None:
    """Return parsed handoff-state.json, or None if the file is missing."""
    p = _handoff_dir(base) / "handoff-state.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Corrupted handoff state at {p}: {exc}. "
            "Run 'agent-co-op handoff clear' to reset."
        ) from exc


def read_current_handoff(base: Path | None = None) -> str | None:
    """Return the contents of CURRENT_HANDOFF.md, or None if missing."""
    p = _handoff_dir(base) / "CURRENT_HANDOFF.md"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")
