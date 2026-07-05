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


def _apply_project_role_overrides(
    routing: dict[str, Any],
    project: dict[str, Any] | None,
    role: str,
) -> dict[str, Any]:
    """Merge optional per-role overrides from a project manifest."""
    if project is None:
        return routing

    role_config = project.get("roles", {}).get(role, {})
    if not isinstance(role_config, dict):
        return routing

    updated = dict(routing)
    for key in ("agent", "model_tier"):
        if key in role_config:
            updated[key] = role_config[key]

    if "work_mode" in role_config:
        work_mode = role_config["work_mode"]
        if work_mode not in VALID_WORK_MODES:
            raise ValueError(
                f"Unknown work_mode {work_mode!r} in project manifest for role {role!r}. "
                f"Valid work modes: {sorted(VALID_WORK_MODES)}"
            )
        defaults = load_defaults()
        work_mode_info = defaults["work_modes"].get(work_mode, {})
        updated["work_mode"] = work_mode
        updated["work_mode_description"] = work_mode_info.get("description", "")
        updated["context_discipline"] = work_mode_info.get("context", [])
        updated["tool_discipline"] = work_mode_info.get("tools", [])

    return updated


def resolve_routing(
    role: str,
    phase: str | None = None,
    project_id: str | None = None,
    base: Path | None = None,
) -> dict[str, Any]:
    """Return full routing information for a role and optional phase.

    Returns a dict with keys: role, phase, project_id, work_mode,
    work_mode_description, context_discipline, tool_discipline, agent, model_tier.

    When ``project_id`` is set, loads ``.agent-co-op/<project_id>.json`` (or
    ``project.json``) and merges per-role overrides (agent, model_tier, work_mode).

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

    routing: dict[str, Any] = {
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

    if project_id is not None:
        from .project_store import load_project

        project = load_project(project_id, base=base)
        routing = _apply_project_role_overrides(routing, project, role)

    return routing
