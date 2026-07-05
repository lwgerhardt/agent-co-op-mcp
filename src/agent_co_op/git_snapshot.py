"""Capture git workspace metadata for handoff state."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _git_output(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def current_branch(base: Path | None = None) -> str | None:
    """Return the current git branch, or None when not in a git repo."""
    root = base or Path.cwd()
    branch = _git_output(["branch", "--show-current"], root)
    return branch if branch else None


def capture_git_snapshot(
    base: Path | None = None,
    base_branch: str = "main",
) -> dict[str, Any] | None:
    """Capture git state when inside a repo; return None otherwise."""
    root = base or Path.cwd()
    if _git_output(["rev-parse", "--is-inside-work-tree"], root) != "true":
        return None

    branch = current_branch(base) or ""
    last_commit = _git_output(["log", "-1", "--format=%h %s"], root) or ""
    status = _git_output(["status", "--porcelain"], root)
    modified_files: list[str] = []
    uncommitted = False
    if status is not None:
        uncommitted = bool(status)
        for line in status.splitlines():
            if len(line) >= 4:
                modified_files.append(line[3:])

    return {
        "branch": branch,
        "base_branch": base_branch,
        "modified_files": modified_files,
        "uncommitted": uncommitted,
        "last_commit": last_commit,
    }


def _append_git_label(lines: list[str], label: str, value: Any) -> None:
    if isinstance(value, str) and value:
        lines.append(f"**{label}:** {value}")


def _append_modified_files(lines: list[str], modified: Any) -> None:
    if not isinstance(modified, list) or not modified:
        return
    lines.append("**Modified files:**")
    paths = [path for path in modified[:10] if isinstance(path, str)]
    lines.extend(f"- {path}" for path in paths)
    if len(modified) > 10:
        lines.append(f"- … and {len(modified) - 10} more")


def format_git_section_lines(git: dict[str, Any]) -> list[str]:
    """Render git snapshot metadata as markdown lines."""
    lines = ["", "## Git"]
    _append_git_label(lines, "Branch", git.get("branch"))
    _append_git_label(lines, "Last commit", git.get("last_commit"))
    if git.get("uncommitted"):
        lines.append("**Uncommitted changes:** yes")
        _append_modified_files(lines, git.get("modified_files"))
    return lines
