"""Thin stdio MCP server wrapping core agent-co-op modules.

All log output goes to stderr only; tool handlers delegate to core modules.
Expected failures use ToolError/ResourceError so clients receive actionable
messages (see MCP best practices). Unexpected failures are masked when
``mask_error_details=True``.
"""

from __future__ import annotations

import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ResourceError, ToolError

from . import handoff as _handoff
from . import projects as _projects
from .handoff.core import HandoffUpdateError
from .mcp_support import (
    SERVER_INSTRUCTIONS,
    SERVER_NAME,
    dumps_json,
    normalize_context,
    raise_tool_errors,
    require_resource,
    resolve_workspace_base,
)
from .routing import phase_to_role, resolve_routing
from .verification import VerificationError

# Backward-compatible alias for tests.
_resolve_base = resolve_workspace_base

mcp = FastMCP(
    SERVER_NAME,
    instructions=SERVER_INSTRUCTIONS,
)


@mcp.resource("handoff://status", mime_type="application/json")
def resource_handoff_status() -> str:
    """Compact JSON status of the current handoff."""
    return dumps_json(_handoff.handoff_status(base=resolve_workspace_base("")))


@mcp.resource("handoff://current", mime_type="text/markdown")
def resource_handoff_current() -> str:
    """Rendered CURRENT_HANDOFF.md for the active handoff."""
    current = require_resource(
        _handoff.read_current_handoff(base=resolve_workspace_base("")),
        "No active handoff.",
    )
    return current


@mcp.resource("handoff://state", mime_type="application/json")
def resource_handoff_state() -> str:
    """Full handoff-state.json contents."""
    try:
        state = _handoff.read_state(base=resolve_workspace_base(""))
    except ValueError as exc:
        raise ResourceError(str(exc)) from exc
    state = require_resource(state, "No handoff state.")
    return dumps_json(state)


@mcp.resource("handoff://project/{project_id}", mime_type="application/json")
def resource_handoff_project(project_id: str) -> str:
    """Project manifest summary JSON."""
    try:
        summary = _projects.project_summary(
            project_id,
            base=resolve_workspace_base(""),
        )
    except FileNotFoundError as exc:
        raise ResourceError(str(exc)) from exc
    return dumps_json(summary)


@mcp.resource("handoff://queue", mime_type="application/json")
def resource_handoff_queue() -> str:
    """Verification queue JSON."""
    from . import verification as _verification

    try:
        queue = _verification.load_queue(base=resolve_workspace_base(""))
    except VerificationError as exc:
        raise ResourceError(str(exc)) from exc
    queue = require_resource(queue, "No verification queue found.")
    return dumps_json(queue)


@mcp.resource("handoff://report", mime_type="application/json")
def resource_handoff_report() -> str:
    """Latest verification report JSON summary."""
    from . import verification as _verification

    report = _verification.verification_report(base=resolve_workspace_base(""))
    if not report["found"]:
        raise ResourceError("No verification report found.")
    return dumps_json(report["summary"])


@mcp.tool()
@raise_tool_errors(FileNotFoundError)
def handoff_pickup(project_id: str = "", workspace_path: str = "") -> str:
    """Return a paste-ready pickup prompt for the current handoff state."""
    return _projects.pickup(
        project_id=project_id or None,
        base=resolve_workspace_base(workspace_path),
    )


@mcp.tool()
@raise_tool_errors(FileNotFoundError, ValueError)
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
        base=resolve_workspace_base(workspace_path),
    )


@mcp.tool()
@raise_tool_errors(ValueError, OSError)
def handoff_publish(
    objective: str,
    phase: str,
    project_id: str,
    next_steps: list[str] | None = None,
    context: Any = None,
    workspace_path: str = "",
) -> str:
    """Publish a handoff state."""
    _handoff.publish(
        objective,
        phase,
        project_id,
        next_steps=next_steps or None,
        context=normalize_context(context),
        base=resolve_workspace_base(workspace_path),
    )
    return f"Handoff published for {project_id} / {phase}."


@mcp.tool()
@raise_tool_errors(HandoffUpdateError, FileNotFoundError, ValueError)
def handoff_update(
    objective: str = "",
    phase: str = "",
    next_steps: list[str] | None = None,
    append_next_steps: list[str] | None = None,
    context: Any = None,
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
        context=normalize_context(context),
        clear_context=clear_context,
        clear_next_steps=clear_next_steps,
        base=resolve_workspace_base(workspace_path),
    )
    return dumps_json(state)


@mcp.tool()
def handoff_clear(workspace_path: str = "") -> str:
    """Clear all handoff files from .agent-co-op/."""
    _handoff.clear(base=resolve_workspace_base(workspace_path))
    return "Handoff files cleared."


@mcp.tool()
@raise_tool_errors(ValueError)
def handoff_status(workspace_path: str = "") -> str:
    """Return the current handoff state as JSON."""
    return dumps_json(
        _handoff.handoff_status(base=resolve_workspace_base(workspace_path))
    )


@mcp.tool()
@raise_tool_errors(ValueError)
def handoff_history(
    limit: int = 0,
    entry_id: str = "",
    workspace_path: str = "",
) -> str:
    """Return archived handoff history as JSON."""
    base = resolve_workspace_base(workspace_path)
    if entry_id:
        entry = _handoff.read_history_entry(entry_id, base=base)
        if entry is None:
            raise ToolError(f"No history entry found for {entry_id!r}.")
        return dumps_json(entry)
    history_limit = limit if limit > 0 else None
    return dumps_json(_handoff.handoff_history(limit=history_limit, base=base))


@mcp.tool()
@raise_tool_errors(FileNotFoundError, ValueError)
def handoff_restore(entry_id: str, workspace_path: str = "") -> str:
    """Restore a prior handoff state from history as the current handoff."""
    state = _handoff.restore(entry_id, base=resolve_workspace_base(workspace_path))
    return dumps_json(state)


@mcp.tool()
@raise_tool_errors(FileNotFoundError, ValueError)
def project_show(project_id: str, workspace_path: str = "") -> str:
    """Show project manifest metadata and configured roles."""
    base = resolve_workspace_base(workspace_path)
    return dumps_json(_projects.project_summary(project_id, base=base))


@mcp.tool()
@raise_tool_errors(FileExistsError, OSError, ValueError)
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
        base=resolve_workspace_base(workspace_path),
    )
    return dumps_json(result)


@mcp.tool()
@raise_tool_errors(FileNotFoundError, ValueError)
def project_validate(project_id: str, workspace_path: str = "") -> str:
    """Validate a project manifest and return a JSON report."""
    base = resolve_workspace_base(workspace_path)
    return dumps_json(_projects.validate_project(project_id, base=base))


@mcp.tool()
@raise_tool_errors(
    FileNotFoundError,
    VerificationError,
    ValueError,
    OSError,
)
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

    base = resolve_workspace_base(workspace_path)
    queue = _verification.publish_for_verifier(
        objective,
        project_id,
        profile_id=profile_id,
        next_steps=next_steps or None,
        context=normalize_context(context),
        base=base,
    )
    return dumps_json(
        {
            "status": "published",
            "project_id": project_id,
            "profile_id": queue["profile_id"],
            "queue_path": str(_verification.queue_path(base)),
        }
    )


@mcp.tool()
@raise_tool_errors(FileNotFoundError, VerificationError)
def handoff_run_verification(
    profile_id: str = "",
    project_id: str = "",
    continue_on_failure: bool = False,
    workspace_path: str = "",
) -> str:
    """Run verification queue and return PASS/FAIL summary JSON."""
    from . import verification as _verification

    summary = _verification.run_verification(
        profile_id=profile_id or None,
        project_id=project_id or None,
        stop_on_failure=not continue_on_failure,
        base=resolve_workspace_base(workspace_path),
    )
    return dumps_json(summary)


@mcp.tool()
def handoff_verification_report(workspace_path: str = "") -> str:
    """Return latest verification report metadata and summary."""
    from . import verification as _verification

    return dumps_json(
        _verification.verification_report(base=resolve_workspace_base(workspace_path))
    )


@mcp.tool()
@raise_tool_errors(ValueError)
def routing_show(
    project_id: str,
    phase: str = "",
    workspace_path: str = "",
) -> str:
    """Show routing info for a project and optional phase."""
    base = resolve_workspace_base(workspace_path)
    phase_value: str | None = phase or None
    role = phase_to_role(phase_value) if phase_value else "planner"
    info = resolve_routing(role, phase=phase_value, project_id=project_id, base=base)
    return dumps_json(info)


def main() -> None:
    """Run the MCP server over stdio."""
    print("agent-co-op MCP server starting (stdio)", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
