"""Build paste-ready role and pickup prompt markdown sections."""

from __future__ import annotations

from typing import Any


def nonempty_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def append_bullet_section(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines += ["", f"## {title}"]
    lines.extend(f"- {item}" for item in items)


def append_labeled_section(
    lines: list[str],
    title: str,
    fields: list[tuple[str, str | None]],
) -> None:
    section = [
        f"**{label}:** {value}" for label, value in fields if value is not None
    ]
    if not section:
        return
    lines += ["", f"## {title}", *section]


def role_notes(project: dict[str, Any] | None, role: str) -> str | None:
    if project is None:
        return None
    roles = project.get("roles", {})
    if not isinstance(roles, dict):
        return None
    role_config = roles.get(role, {})
    if not isinstance(role_config, dict):
        return None
    notes = role_config.get("notes")
    return notes if isinstance(notes, str) and notes.strip() else None


def normalize_bootstrap_commands(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def format_read_map_entry(entry: Any) -> str | None:
    if isinstance(entry, str) and entry.strip():
        return entry.strip()
    if isinstance(entry, dict):
        file_path = entry.get("file")
        if not isinstance(file_path, str) or not file_path.strip():
            return None
        parts = [file_path.strip()]
        lines = entry.get("lines")
        if isinstance(lines, str) and lines.strip():
            parts.append(lines.strip())
        why = entry.get("why")
        if isinstance(why, str) and why.strip():
            parts.append(f"— {why.strip()}")
        return " ".join(parts)
    return None


def append_project_context(
    lines: list[str],
    project: dict[str, Any] | None,
    project_id: str,
) -> None:
    if project is None:
        return
    fields = [
        ("Name", nonempty_str(project.get("name")) or nonempty_str(project.get("title"))),
        ("Description", nonempty_str(project.get("description"))),
        ("Repository", nonempty_str(project.get("repository"))),
        ("Status", nonempty_str(project.get("status"))),
        ("Branch", nonempty_str(project.get("branch"))),
        ("Verification profile", nonempty_str(project.get("verification_profile"))),
    ]
    if not any(value for _, value in fields):
        fields = [("ID", project_id)]
    append_labeled_section(lines, "Project", fields)


def append_workflow_context(
    lines: list[str],
    project: dict[str, Any] | None,
    role: str,
) -> None:
    if project is None:
        return

    bootstrap = normalize_bootstrap_commands(project.get("bootstrap"))
    if bootstrap:
        append_bullet_section(lines, "Bootstrap", [f"`{command}`" for command in bootstrap])

    read_map = project.get("read_map")
    if isinstance(read_map, list):
        entries = [
            formatted
            for item in read_map
            if (formatted := format_read_map_entry(item)) is not None
        ]
        append_bullet_section(lines, "Files to read", entries)

    role_note_fields = {
        "planner": nonempty_str(project.get("planner_notes")),
        "verifier": nonempty_str(project.get("verifier_notes")),
    }
    notes = role_note_fields.get(role)
    if notes:
        lines += ["", f"## {role.title()} notes", notes]


def append_handoff_state_context(
    lines: list[str],
    state: dict[str, Any],
    project_id: str,
) -> None:
    if state.get("project_id") != project_id:
        active_project = state.get("project_id", "unknown")
        lines += [
            "",
            "## Note",
            (
                f"Handoff state exists for a different project ({active_project!r}). "
                "Run 'agent-co-op handoff clear' to reset, or "
                "'agent-co-op handoff history' to inspect."
            ),
        ]
        return

    lines += [
        "",
        "## Current objective",
        state.get("objective", "(none)"),
    ]
    handoff_context = state.get("context")
    if isinstance(handoff_context, str) and handoff_context.strip():
        lines += ["", "## Handoff context", handoff_context.strip()]
    elif isinstance(handoff_context, dict):
        from .handoff_context import format_context_sections, parse_context

        lines += format_context_sections(parse_context(state))
    git_block = state.get("git")
    if isinstance(git_block, dict):
        from .git_snapshot import format_git_section_lines

        lines += format_git_section_lines(git_block)
    next_steps: list[str] = state.get("next_steps", [])
    if next_steps:
        lines += ["", "## Next steps"]
        for step in next_steps:
            lines.append(f"- {step}")


def build_role_prompt(
    *,
    project_id: str,
    role: str,
    phase: str | None,
    project: dict[str, Any] | None,
    routing: dict[str, Any],
    state: dict[str, Any] | None,
) -> str:
    """Assemble a paste-ready role prompt from routing and optional handoff state."""
    lines: list[str] = [
        f"# Role prompt — {role} / {project_id}",
        "",
        f"**Role:** {role}",
        f"**Agent:** {routing['agent']}",
        f"**Model tier:** {routing['model_tier']}",
        f"**Work mode:** {routing['work_mode']} — {routing['work_mode_description']}",
    ]
    if phase:
        lines.append(f"**Phase:** {phase}")
    append_project_context(lines, project, project_id)
    append_workflow_context(lines, project, role)
    notes = role_notes(project, role)
    if notes:
        lines += ["", "## Role notes", notes]
    lines += ["", "## Context discipline"]
    for bullet in routing["context_discipline"]:
        lines.append(f"- {bullet}")
    lines += ["", "## Tool discipline"]
    for bullet in routing["tool_discipline"]:
        lines.append(f"- {bullet}")
    if state:
        append_handoff_state_context(lines, state, project_id)
    return "\n".join(lines) + "\n"
