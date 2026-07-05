"""Load project manifests from .agent-co-op/ without routing dependencies."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .workspace_paths import handoff_dir

_SAFE_PROJECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def validate_project_id(project_id: str) -> None:
    """Raise ValueError when ``project_id`` is not a safe manifest filename stem."""
    if not _SAFE_PROJECT_ID.fullmatch(project_id):
        raise ValueError(
            f"Invalid project id {project_id!r}. "
            "Use letters, numbers, dots, underscores, or hyphens; "
            "must start with a letter or number."
        )


def find_manifest_path(project_id: str, base: Path | None = None) -> Path | None:
    """Return the manifest path for a project id, or None if missing."""
    validate_project_id(project_id)
    root = handoff_dir(base)
    for candidate in (root / f"{project_id}.json", root / "project.json"):
        if candidate.exists():
            return candidate
    return None


def load_project(project_id: str, base: Path | None = None) -> dict[str, Any] | None:
    """Load a project manifest from .agent-co-op/.

    Looks for <project_id>.json then project.json under <base>/.agent-co-op/.
    Returns None if no manifest is found.
    """
    path = find_manifest_path(project_id, base=base)
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))
