"""Capture, publish, and clear handoff state files in .agent-co-op/."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HANDOFF_DIRNAME = ".agent-co-op"


def _handoff_dir(base: Path | None = None) -> Path:
    return (base or Path.cwd()) / _HANDOFF_DIRNAME


def publish(
    objective: str,
    phase: str,
    project_id: str,
    next_steps: list[str] | None = None,
    base: Path | None = None,
) -> None:
    """Write handoff-state.json, handoff.md, and CURRENT_HANDOFF.md.

    Files are written under <base>/.agent-co-op/ (defaults to cwd).
    Raises ValueError for unknown phases.
    """
    from .routing import phase_to_role, resolve_routing

    role = phase_to_role(phase)
    routing = resolve_routing(role, phase=phase)
    steps: list[str] = next_steps or []

    d = _handoff_dir(base)
    d.mkdir(parents=True, exist_ok=True)

    state: dict[str, Any] = {
        "phase": phase,
        "objective": objective,
        "project_id": project_id,
        "role": role,
        "work_mode": routing["work_mode"],
        "next_steps": steps,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    (d / "handoff-state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )

    summary_md = _render_handoff_md(state, routing)
    (d / "handoff.md").write_text(summary_md, encoding="utf-8")
    (d / "CURRENT_HANDOFF.md").write_text(summary_md, encoding="utf-8")


def _render_handoff_md(state: dict[str, Any], routing: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# Handoff — {state['project_id']} / {state['phase']}",
        "",
        f"**Objective:** {state['objective']}",
        f"**Phase:** {state['phase']}",
        f"**Role:** {state['role']}",
        f"**Work mode:** {state['work_mode']} — {routing['work_mode_description']}",
        "",
        "## Context discipline",
    ]
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
    return "\n".join(lines) + "\n"


def clear(base: Path | None = None) -> None:
    """Remove all handoff files from .agent-co-op/."""
    d = _handoff_dir(base)
    for name in ("handoff-state.json", "handoff.md", "CURRENT_HANDOFF.md"):
        p = d / name
        if p.exists():
            p.unlink()


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
