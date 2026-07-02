"""Thin stdio MCP server wrapping core agent-co-op modules.

All log output goes to stderr only; tool handlers delegate to core modules.
"""

from __future__ import annotations

import json
import sys

from mcp.server.fastmcp import FastMCP

from . import handoff as _handoff
from . import projects as _projects
from .routing import phase_to_role, resolve_routing

mcp = FastMCP("agent-co-op")


@mcp.tool()
def handoff_pickup(project_id: str = "") -> str:
    """Return a paste-ready pickup prompt for the current handoff state."""
    return _projects.pickup(project_id=project_id or None)


@mcp.tool()
def handoff_role_prompt(project_id: str, role: str, phase: str = "") -> str:
    """Return a paste-ready role-prompt for the given project, role, and phase."""
    return _projects.role_prompt(project_id, role, phase=phase or None)


@mcp.tool()
def handoff_publish(
    objective: str,
    phase: str,
    project_id: str,
    next_steps: list[str] | None = None,
) -> str:
    """Publish a handoff state."""
    _handoff.publish(objective, phase, project_id, next_steps=next_steps or None)
    return f"Handoff published for {project_id} / {phase}."


@mcp.tool()
def handoff_clear() -> str:
    """Clear all handoff files from .agent-co-op/."""
    _handoff.clear()
    return "Handoff files cleared."


@mcp.tool()
def handoff_status() -> str:
    """Return the current handoff state as JSON."""
    return json.dumps(_handoff.handoff_status(), indent=2)


@mcp.tool()
def handoff_history(limit: int = 0, entry_id: str = "") -> str:
    """Return archived handoff history as JSON."""
    if entry_id:
        entry = _handoff.read_history_entry(entry_id)
        if entry is None:
            return json.dumps({"error": f"No history entry found for {entry_id!r}."})
        return json.dumps(entry, indent=2)
    history_limit = limit if limit > 0 else None
    return json.dumps(_handoff.handoff_history(limit=history_limit), indent=2)


@mcp.tool()
def project_show(project_id: str) -> str:
    """Show project manifest metadata and configured roles."""
    return json.dumps(_projects.project_summary(project_id), indent=2)


@mcp.tool()
def project_init(
    project_id: str,
    name: str = "",
    description: str = "",
    repository: str = "",
    update_gitignore: bool = True,
) -> str:
    """Create a starter project manifest and optional .gitignore entries."""
    result = _projects.init_workspace(
        project_id,
        name=name or None,
        description=description,
        repository=repository or None,
        update_gitignore=update_gitignore,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def project_validate(project_id: str) -> str:
    """Validate a project manifest and return a JSON report."""
    return json.dumps(_projects.validate_project(project_id), indent=2)


@mcp.tool()
def routing_show(project_id: str, phase: str = "") -> str:
    """Show routing info for a project and optional phase."""
    p: str | None = phase or None
    role = phase_to_role(p) if p else "planner"
    info = resolve_routing(role, phase=p, project_id=project_id)
    return json.dumps(info, indent=2)


def main() -> None:
    """Run the MCP server over stdio."""
    print("agent-co-op MCP server starting (stdio)", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
