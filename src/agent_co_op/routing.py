"""Roles, work modes, phase-to-role mapping, and routing resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULTS_PATH = Path(__file__).parent / "defaults.json"

VALID_ROLES: frozenset[str] = frozenset(
    {"scaffold", "planner", "verifier", "efficiency", "resume"}
)
VALID_PHASES: frozenset[str] = frozenset({"plan", "implement", "verify", "resume"})
VALID_WORK_MODES: frozenset[str] = frozenset(
    {"background", "think", "longContext", "default"}
)

_PHASE_ROLE_MAP: dict[str, str] = {
    "plan": "planner",
    "implement": "verifier",
    "verify": "verifier",
    "resume": "resume",
}


def load_defaults() -> dict[str, Any]:
    """Load and return the defaults.json configuration."""
    with DEFAULTS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def phase_to_role(phase: str) -> str:
    """Return the default role for a given phase.

    Raises ValueError for unknown phases.
    """
    if phase not in VALID_PHASES:
        raise ValueError(
            f"Unknown phase {phase!r}. Valid phases: {sorted(VALID_PHASES)}"
        )
    return _PHASE_ROLE_MAP[phase]


def resolve_work_mode(role: str, phase: str | None = None) -> str:
    """Return the effective work mode for a role, optionally overridden by phase.

    Phase overrides take precedence over the role's default work mode.
    Raises ValueError for unknown roles or phases.
    """
    if role not in VALID_ROLES:
        raise ValueError(
            f"Unknown role {role!r}. Valid roles: {sorted(VALID_ROLES)}"
        )
    if phase is not None and phase not in VALID_PHASES:
        raise ValueError(
            f"Unknown phase {phase!r}. Valid phases: {sorted(VALID_PHASES)}"
        )

    defaults = load_defaults()

    if phase is not None:
        override = (
            defaults.get("phase_work_mode_overrides", {}).get(phase, {}).get(role)
        )
        if override:
            return override

    return defaults["role_work_modes"].get(role, "default")


def resolve_routing(
    role: str,
    phase: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Return full routing information for a role and optional phase.

    Returns a dict with keys: role, phase, project_id, work_mode,
    work_mode_description, context_discipline, tool_discipline, agent, model_tier.

    Raises ValueError for unknown roles or phases.
    """
    if role not in VALID_ROLES:
        raise ValueError(
            f"Unknown role {role!r}. Valid roles: {sorted(VALID_ROLES)}"
        )

    defaults = load_defaults()
    work_mode = resolve_work_mode(role, phase)
    work_mode_info = defaults["work_modes"].get(work_mode, {})
    role_defaults = defaults["defaults"].get(role, {})

    return {
        "role": role,
        "phase": phase,
        "project_id": project_id,
        "work_mode": work_mode,
        "work_mode_description": work_mode_info.get("description", ""),
        "context_discipline": work_mode_info.get("context", []),
        "tool_discipline": work_mode_info.get("tools", []),
        "agent": role_defaults.get("agent", ""),
        "model_tier": role_defaults.get("model_tier", ""),
    }
