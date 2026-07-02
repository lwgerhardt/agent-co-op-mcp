"""Project manifests, role-prompt generation, and pickup logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .routing import resolve_routing, phase_to_role


def load_project(project_id: str, base: Path | None = None) -> dict[str, Any] | None:
    """Load a project manifest from .agent-co-op/.

    Looks for <project_id>.json then project.json under <base>/.agent-co-op/.
    Returns None if no manifest is found.
    """
    d = (base or Path.cwd()) / ".agent-co-op"
    for candidate in (d / f"{project_id}.json", d / "project.json"):
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return None


def role_prompt(
    project_id: str,
    role: str,
    phase: str | None = None,
    base: Path | None = None,
) -> str:
    """Build and return a paste-ready role-prompt string.

    Includes role, agent hint, model tier hint, work mode with discipline bullets,
    and current objective/next-steps from handoff state (if present).

    Raises ValueError for unknown roles or phases.
    """
    from .handoff import read_state

    routing = resolve_routing(role, phase=phase, project_id=project_id)
    state = read_state(base)

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
    lines += ["", "## Context discipline"]
    for bullet in routing["context_discipline"]:
        lines.append(f"- {bullet}")
    lines += ["", "## Tool discipline"]
    for bullet in routing["tool_discipline"]:
        lines.append(f"- {bullet}")

    if state:
        lines += [
            "",
            "## Current objective",
            state.get("objective", "(none)"),
        ]
        next_steps: list[str] = state.get("next_steps", [])
        if next_steps:
            lines += ["", "## Next steps"]
            for step in next_steps:
                lines.append(f"- {step}")

    return "\n".join(lines) + "\n"


def pickup(project_id: str | None = None, base: Path | None = None) -> str:
    """Return a paste-ready pickup prompt derived from current handoff state.

    Raises FileNotFoundError if no handoff state exists; ValueError if state is invalid.
    """
    from .handoff import read_state

    state = read_state(base)
    if state is None:
        raise FileNotFoundError(
            "No handoff state found. Run 'agent-co-op handoff publish' first."
        )

    pid = project_id or state.get("project_id", "unknown")
    phase = state.get("phase", "resume")
    role = state.get("role") or phase_to_role(phase)

    return role_prompt(pid, role, phase=phase, base=base)
