"""Thin stdio MCP server wrapping core agent-co-op modules.

All log output goes to stderr only; tool handlers delegate to core modules.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import handoff as _handoff
from . import projects as _projects
from .routing import phase_to_role, resolve_routing

mcp = FastMCP("agent-co-op")


def _resolve_base(workspace_path: str = "") -> Path | None:
    """Resolve workspace root for MCP tool calls."""
    if workspace_path:
        return Path(workspace_path)
    if env_root := os.environ.get("AGENT_CO_OP_ROOT"):
        return Path(env_root)
    return None


def _normalize_context(value: Any) -> str | dict[str, Any] | None:
    """Accept plain text or structured v2 context from MCP callers."""
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return stripped
            if isinstance(parsed, dict):
                return parsed
        return stripped
    return None


@mcp.resource("handoff://status")
def resource_handoff_status() -> str:
    """Compact JSON status of the current handoff."""
    return json.dumps(_handoff.handoff_status(base=_resolve_base("")), indent=2)


@mcp.resource("handoff://current")
def resource_handoff_current() -> str:
    """Rendered CURRENT_HANDOFF.md for the active handoff."""
    current = _handoff.read_current_handoff(base=_resolve_base(""))
    if current is None:
        return json.dumps({"error": "No active handoff."})
    return current


@mcp.resource("handoff://state")
def resource_handoff_state() -> str:
    """Full handoff-state.json contents."""
    state = _handoff.read_state(base=_resolve_base(""))
    if state is None:
        return json.dumps({"error": "No handoff state."})
    return json.dumps(state, indent=2)


@mcp.resource("handoff://project/{project_id}")
def resource_handoff_project(project_id: str) -> str:
    """Project manifest summary JSON."""
    try:
        summary = _projects.project_summary(
            project_id,
            base=_resolve_base(""),
        )
    except FileNotFoundError:
        return json.dumps(
            {"error": f"No project manifest found for {project_id!r}."}
        )
    return json.dumps(summary, indent=2)


@mcp.resource("handoff://queue")
def resource_handoff_queue() -> str:
    """Verification queue JSON."""
    from . import verification as _verification

    try:
        queue = _verification.load_queue(base=_resolve_base(""))
    except _verification.VerificationError as exc:
        return json.dumps({"error": str(exc)})
    if queue is None:
        return json.dumps({"error": "No verification queue found."})
    return json.dumps(queue, indent=2)


@mcp.resource("handoff://report")
def resource_handoff_report() -> str:
    """Latest verification report JSON summary."""
    from . import verification as _verification

    report = _verification.verification_report(base=_resolve_base(""))
    if not report["found"]:
        return json.dumps({"error": "No verification report found."})
    return json.dumps(report["summary"], indent=2)


@mcp.tool()
def handoff_pickup(project_id: str = "", workspace_path: str = "") -> str:
    """Return a paste-ready pickup prompt for the current handoff state."""
    return _projects.pickup(
        project_id=project_id or None,
        base=_resolve_base(workspace_path),
    )


@mcp.tool()
def handoff_role_prompt(
    project_id: str,
    role: str,
    phase: str = "",
    workspace_path: str = "",
) -> str:
    """Return a paste-ready role-prompt for the given project, role, and phase."""
    return _projects.role_prompt(
        project_id,
        role,
        phase=phase or None,
        base=_resolve_base(workspace_path),
    )


@mcp.tool()
def handoff_publish(
    objective: str,
    phase: str,
    project_id: str,
    next_steps: list[str] | None = None,
    context: str = "",
    workspace_path: str = "",
) -> str:
    """Publish a handoff state."""
    _handoff.publish(
        objective,
        phase,
        project_id,
        next_steps=next_steps or None,
        context=context or None,
        base=_resolve_base(workspace_path),
    )
    return f"Handoff published for {project_id} / {phase}."


@mcp.tool()
def handoff_update(
    objective: str = "",
    phase: str = "",
    next_steps: list[str] | None = None,
    append_next_steps: list[str] | None = None,
    context: str = "",
    clear_context: bool = False,
    clear_next_steps: bool = False,
    workspace_path: str = "",
) -> str:
    """Patch the current handoff state without a full republish."""
    state = _handoff.update(
        objective=objective or None,
        phase=phase or None,
        next_steps=next_steps,
        append_next_steps=append_next_steps,
        context=context or None,
        clear_context=clear_context,
        clear_next_steps=clear_next_steps,
        base=_resolve_base(workspace_path),
    )
    return json.dumps(state, indent=2)


@mcp.tool()
def handoff_clear(workspace_path: str = "") -> str:
    """Clear all handoff files from .agent-co-op/."""
    _handoff.clear(base=_resolve_base(workspace_path))
    return "Handoff files cleared."


@mcp.tool()
def handoff_status(workspace_path: str = "") -> str:
    """Return the current handoff state as JSON."""
    return json.dumps(
        _handoff.handoff_status(base=_resolve_base(workspace_path)),
        indent=2,
    )


@mcp.tool()
def handoff_history(
    limit: int = 0,
    entry_id: str = "",
    workspace_path: str = "",
) -> str:
    """Return archived handoff history as JSON."""
    base = _resolve_base(workspace_path)
    if entry_id:
        entry = _handoff.read_history_entry(entry_id, base=base)
        if entry is None:
            return json.dumps({"error": f"No history entry found for {entry_id!r}."})
        return json.dumps(entry, indent=2)
    history_limit = limit if limit > 0 else None
    return json.dumps(_handoff.handoff_history(limit=history_limit, base=base), indent=2)


@mcp.tool()
def handoff_restore(entry_id: str, workspace_path: str = "") -> str:
    """Restore a prior handoff state from history as the current handoff."""
    state = _handoff.restore(entry_id, base=_resolve_base(workspace_path))
    return json.dumps(state, indent=2)


@mcp.tool()
def project_show(project_id: str, workspace_path: str = "") -> str:
    """Show project manifest metadata and configured roles."""
    return json.dumps(
        _projects.project_summary(project_id, base=_resolve_base(workspace_path)),
        indent=2,
    )


@mcp.tool()
def project_init(
    project_id: str,
    name: str = "",
    description: str = "",
    repository: str = "",
    update_gitignore: bool = True,
    workspace_path: str = "",
) -> str:
    """Create a starter project manifest and optional .gitignore entries."""
    result = _projects.init_workspace(
        project_id,
        name=name or None,
        description=description,
        repository=repository or None,
        update_gitignore=update_gitignore,
        base=_resolve_base(workspace_path),
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def project_validate(project_id: str, workspace_path: str = "") -> str:
    """Validate a project manifest and return a JSON report."""
    return json.dumps(
        _projects.validate_project(project_id, base=_resolve_base(workspace_path)),
        indent=2,
    )


@mcp.tool()
def handoff_publish_for_verifier(
    objective: str,
    project_id: str,
    profile_id: str = "default",
    next_steps: list[str] | None = None,
    context: Any = None,
    workspace_path: str = "",
) -> str:
    """Publish implement-phase handoff and write verification queue."""
    from . import verification as _verification

    try:
        queue = _verification.publish_for_verifier(
            objective,
            project_id,
            profile_id=profile_id,
            next_steps=next_steps or None,
            context=_normalize_context(context),
            base=_resolve_base(workspace_path),
        )
    except (FileNotFoundError, _verification.VerificationError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(
        {
            "status": "published",
            "project_id": project_id,
            "profile_id": queue["profile_id"],
            "queue_path": str(_verification.queue_path(_resolve_base(workspace_path))),
        },
        indent=2,
    )


@mcp.tool()
def handoff_run_verification(
    profile_id: str = "",
    project_id: str = "",
    continue_on_failure: bool = False,
    workspace_path: str = "",
) -> str:
    """Run verification queue and return PASS/FAIL summary JSON."""
    from . import verification as _verification

    try:
        summary = _verification.run_verification(
            profile_id=profile_id or None,
            project_id=project_id or None,
            stop_on_failure=not continue_on_failure,
            base=_resolve_base(workspace_path),
        )
    except (FileNotFoundError, _verification.VerificationError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(summary, indent=2)


@mcp.tool()
def handoff_verification_report(workspace_path: str = "") -> str:
    """Return latest verification report metadata and summary."""
    from . import verification as _verification

    return json.dumps(
        _verification.verification_report(base=_resolve_base(workspace_path)),
        indent=2,
    )


@mcp.tool()
def routing_show(
    project_id: str,
    phase: str = "",
    workspace_path: str = "",
) -> str:
    """Show routing info for a project and optional phase."""
    base = _resolve_base(workspace_path)
    p: str | None = phase or None
    role = phase_to_role(p) if p else "planner"
    info = resolve_routing(role, phase=p, project_id=project_id, base=base)
    return json.dumps(info, indent=2)


def main() -> None:
    """Run the MCP server over stdio."""
    print("agent-co-op MCP server starting (stdio)", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
