"""Render handoff markdown from state and routing metadata."""

from __future__ import annotations

from typing import Any


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


def render_handoff_md(state: dict[str, Any], routing: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# Handoff — {state['project_id']} / {state['phase']}",
        "",
        f"**Objective:** {state['objective']}",
        f"**Phase:** {state['phase']}",
        f"**Role:** {state['role']}",
        f"**Work mode:** {state['work_mode']} — {routing['work_mode_description']}",
    ]
    append_rendered_context(lines, state)
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
    append_rendered_timestamps(lines, state)
    return "\n".join(lines) + "\n"
