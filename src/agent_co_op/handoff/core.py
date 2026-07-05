"""Publish, update, and inspect current handoff state."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..git_snapshot import capture_git_snapshot, current_branch
from ..handoff_state import validate_handoff_state
from .history import archive_current_state
from .io import read_current_handoff, read_state, write_handoff_files
from .paths import handoff_paths


class HandoffUpdateError(ValueError):
    """Raised when a handoff update request is invalid."""


def warn_state_schema(state: dict[str, Any]) -> None:
    for warning in validate_handoff_state(state):
        print(f"Warning: handoff state schema: {warning}", file=sys.stderr)


def verification_warning(state: dict[str, Any], base: Path | None = None) -> str | None:
    if state.get("phase") != "implement":
        return None
    next_steps = state.get("next_steps", [])
    if isinstance(next_steps, list) and next_steps:
        return None
    from ..verification import queue_exists

    if queue_exists(base):
        return None
    return (
        "implement phase has no next_steps and no verification queue; "
        "add verification steps before handoff to verifier"
    )


def stale_warning(published_at: str | None, days: int = 7) -> str | None:
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


def branch_mismatch_warning(
    state: dict[str, Any], base: Path | None = None
) -> str | None:
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


def publish(
    objective: str,
    phase: str,
    project_id: str,
    next_steps: list[str] | None = None,
    context: str | dict[str, Any] | None = None,
    base: Path | None = None,
) -> None:
    """Write handoff-state.json, handoff.md, and CURRENT_HANDOFF.md."""
    from ..routing import phase_to_role, resolve_routing

    role = phase_to_role(phase)
    routing = resolve_routing(role, phase=phase, project_id=project_id, base=base)
    steps: list[str] = next_steps or []
    now = datetime.now(timezone.utc).isoformat()

    archive_current_state(base)

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

    git_block = capture_git_snapshot(base)
    if git_block is not None:
        state["git"] = git_block

    warn_state_schema(state)
    write_handoff_files(state, base=base)


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
    from ..routing import phase_to_role, resolve_routing

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
    git_block = capture_git_snapshot(base)
    if git_block is not None:
        state["git"] = git_block
    warn_state_schema(state)
    write_handoff_files(state, base=base)


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
    """Patch the current handoff state without a full republish."""
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
        "paths": handoff_paths(base),
    }
    if state is not None:
        published_at = state.get("published_at")
        if isinstance(published_at, str):
            result["created_at"] = published_at
            stale = stale_warning(published_at)
            if stale:
                result["stale_warning"] = stale
        branch_warning = branch_mismatch_warning(state, base)
        if branch_warning:
            result["branch_mismatch_warning"] = branch_warning
        verify_warning = verification_warning(state, base)
        if verify_warning:
            result["verification_warning"] = verify_warning
        for key in ("phase", "objective", "project_id", "role"):
            if key in state:
                result[key] = state[key]
    return result
