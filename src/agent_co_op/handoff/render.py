"""Render handoff markdown from state and routing metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..prompt_builder import (
    append_project_context,
    format_read_map_entry,
    normalize_bootstrap_commands,
    role_notes,
)

_PHASE_BANNERS: dict[str, str] = {
    "plan": (
        "**Phase: plan** — Implementation not finished. "
        "Run bootstrap before broad file reads."
    ),
    "implement": (
        "**Phase: implement** — Verifier owns test execution; "
        "planner must not claim gates passed."
    ),
    "verify": (
        "**Phase: verify** — Run verification commands and report PASS/FAIL."
    ),
    "resume": (
        "**Phase: resume** — Continue from handoff state; bootstrap if stale."
    ),
}


def _load_project(project_id: str, base: Path | None) -> dict[str, Any] | None:
    from ..project_store import load_project

    return load_project(project_id, base=base)


def _read_queue_file(base: Path | None) -> dict[str, Any] | None:
    from ..verification import queue_path

    path = queue_path(base)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _load_queue(base: Path | None) -> dict[str, Any] | None:
    queue = _read_queue_file(base)
    if queue is None:
        return None
    from ..verification import validate_queue_data

    if validate_queue_data(queue)["valid"]:
        return queue
    return queue


def collect_bootstrap_commands(
    state: dict[str, Any],
    project: dict[str, Any] | None,
    queue: dict[str, Any] | None,
) -> list[str]:
    """Merge bootstrap commands from state context, manifest, and queue."""
    seen: set[str] = set()
    commands: list[str] = []

    def add(value: Any) -> None:
        for command in normalize_bootstrap_commands(value):
            if command not in seen:
                seen.add(command)
                commands.append(command)

    context = state.get("context")
    if isinstance(context, dict):
        add(context.get("bootstrap"))
    if project is not None:
        add(project.get("bootstrap"))
    if queue is not None:
        add(queue.get("bootstrap"))
    return commands


def append_phase_banner(lines: list[str], phase: str) -> None:
    banner = _PHASE_BANNERS.get(phase)
    if banner:
        lines += ["", banner]


def append_bootstrap_section(lines: list[str], commands: list[str]) -> None:
    if not commands:
        return
    lines += ["", "## Bootstrap", ""]
    for command in commands:
        lines += ["```bash", command, "```", ""]


def append_verifier_section(
    lines: list[str],
    state: dict[str, Any],
    queue: dict[str, Any] | None,
    *,
    base: Path | None,
) -> None:
    from ..verification import queue_path

    phase = state.get("phase")
    if phase not in ("implement", "verify") and queue is None:
        return

    lines += ["", "## Verifier"]
    if phase == "implement":
        lines.append(
            "Verifier owns test execution. Planner must not claim gates passed "
            "without running `agent-co-op verify run`."
        )
    if queue is not None:
        lines.append(f"**Queue:** `{queue_path(base)}`")
        profile_id = queue.get("profile_id")
        if isinstance(profile_id, str) and profile_id:
            lines.append(f"**Profile:** `{profile_id}`")
    lines.append("**Run:** `agent-co-op verify run`")


def append_routing_table(lines: list[str], routing: dict[str, Any]) -> None:
    rows: list[tuple[str, str]] = []
    for label, key in (
        ("Role", "role"),
        ("Phase", "phase"),
        ("Agent", "agent"),
        ("Model tier", "model_tier"),
        ("Work mode", "work_mode"),
    ):
        value = routing.get(key)
        if value:
            rows.append((label, str(value)))
    if not rows:
        return
    lines += ["", "## Routing", "", "| | |", "|---|---|"]
    for label, value in rows:
        lines.append(f"| {label} | {value} |")


def append_role_notes_section(
    lines: list[str],
    project: dict[str, Any] | None,
    role: str,
) -> None:
    if project is None:
        return
    notes = role_notes(project, role)
    if notes is None:
        root_notes = {
            "planner": project.get("planner_notes"),
            "verifier": project.get("verifier_notes"),
        }.get(role)
        if isinstance(root_notes, str) and root_notes.strip():
            notes = root_notes.strip()
    if notes:
        lines += ["", f"## {role.title()} notes", notes]


def append_manifest_read_map(
    lines: list[str],
    project: dict[str, Any] | None,
    *,
    skip_when_state_has_read_map: bool,
) -> None:
    if skip_when_state_has_read_map or project is None:
        return
    read_map = project.get("read_map")
    if not isinstance(read_map, list):
        return
    entries = [
        formatted
        for item in read_map
        if (formatted := format_read_map_entry(item)) is not None
    ]
    if not entries:
        return
    lines += ["", "## Files to read"]
    lines.extend(f"- {entry}" for entry in entries)


def append_capture_placeholders(lines: list[str], state: dict[str, Any]) -> None:
    context = state.get("context")
    has_todos = isinstance(context, dict) and context.get("todos")
    has_files = isinstance(context, dict) and context.get("files_touched")
    if has_todos and has_files:
        return
    lines += ["", "## Capture"]
    if not has_todos:
        lines += ["", "### Todos", "_(populated by handoff capture)_"]
    if not has_files:
        lines += ["", "### Files touched", "_(populated by handoff capture)_"]


def append_rendered_context(lines: list[str], state: dict[str, Any]) -> None:
    handoff_context = state.get("context")
    if isinstance(handoff_context, str) and handoff_context.strip():
        lines += ["", "## Handoff context", handoff_context.strip()]
    elif isinstance(handoff_context, dict):
        from ..handoff_context import format_context_sections, parse_context

        lines += format_context_sections(parse_context(state))


def append_rendered_timestamps(lines: list[str], state: dict[str, Any]) -> None:
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


def format_git_lines(git: dict[str, Any]) -> list[str]:
    from ..git_snapshot import format_git_section_lines

    return format_git_section_lines(git)


def _state_has_read_map(state: dict[str, Any]) -> bool:
    context = state.get("context")
    if not isinstance(context, dict):
        return False
    read_map = context.get("read_map")
    return isinstance(read_map, list) and len(read_map) > 0


def render_handoff_md(
    state: dict[str, Any],
    routing: dict[str, Any],
    *,
    base: Path | None = None,
) -> str:
    project_id = state["project_id"]
    project = _load_project(project_id, base)
    queue = _load_queue(base)
    bootstrap = collect_bootstrap_commands(state, project, queue)

    lines: list[str] = [
        f"# Handoff — {project_id} / {state['phase']}",
        "",
        f"**Objective:** {state['objective']}",
        f"**Role:** {state['role']}",
        f"**Work mode:** {state['work_mode']} — {routing['work_mode_description']}",
    ]
    append_phase_banner(lines, state["phase"])
    append_project_context(lines, project, project_id)
    append_role_notes_section(lines, project, state["role"])
    append_bootstrap_section(lines, bootstrap)
    append_verifier_section(lines, state, queue, base=base)
    append_routing_table(lines, routing)
    append_rendered_context(lines, state)
    append_manifest_read_map(
        lines,
        project,
        skip_when_state_has_read_map=_state_has_read_map(state),
    )
    git_block = state.get("git")
    if isinstance(git_block, dict):
        lines += format_git_lines(git_block)
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
    append_capture_placeholders(lines, state)
    append_rendered_timestamps(lines, state)
    return "\n".join(lines) + "\n"
