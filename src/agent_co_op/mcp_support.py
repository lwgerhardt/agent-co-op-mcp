"""Shared helpers for the agent-co-op MCP server."""

from __future__ import annotations

import functools
import inspect
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from mcp.server.fastmcp.exceptions import ResourceError, ToolError

T = TypeVar("T")

SERVER_NAME = "agent-co-op"
SERVER_INSTRUCTIONS = """\
Cross-IDE handoff server for .agent-co-op/ workspace files.

Set AGENT_CO_OP_ROOT to the consumer project root (or pass workspace_path on tools).
Prefer read resources (handoff://status, handoff://current) for low-token reads.
Use handoff_pickup or handoff://current to resume work after an IDE switch.
"""


def resolve_workspace_base(workspace_path: str = "") -> Path | None:
    """Resolve the workspace root for MCP tools and resources."""
    if workspace_path:
        path = Path(workspace_path)
        if not path.is_dir():
            raise ToolError(f"workspace_path is not a directory: {workspace_path!r}")
        return path
    if env_root := os.environ.get("AGENT_CO_OP_ROOT"):
        path = Path(env_root)
        if not path.is_dir():
            raise ToolError(
                f"AGENT_CO_OP_ROOT is not a directory: {env_root!r}"
            )
        return path
    return None


def dumps_json(payload: Any) -> str:
    """Serialize MCP JSON payloads with stable formatting."""
    return json.dumps(payload, indent=2)


def normalize_context(value: Any) -> str | dict[str, Any] | None:
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
    raise ToolError("context must be a string or JSON object")


def raise_tool_errors(
    *errors: type[BaseException],
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that converts expected domain errors into ToolError."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except errors as exc:
                raise ToolError(str(exc)) from exc

        wrapper.__signature__ = inspect.signature(func)
        return wrapper

    return decorator


def require_resource(value: T | None, message: str) -> T:
    """Raise ResourceError when a resource payload is missing."""
    if value is None:
        raise ResourceError(message)
    return value
