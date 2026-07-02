"""Shared git repo helpers for tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

git_available = shutil.which("git") is not None

requires_git = pytest.mark.skipif(
    not git_available,
    reason="git executable not available",
)


def init_git_repo(path: Path, branch: str = "main") -> None:
    """Initialize a git repo with one commit, or skip when git is unavailable."""
    if not git_available:
        pytest.skip("git executable not available")

    subprocess.run(["git", "init", "-b", branch], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=path,
        check=True,
        capture_output=True,
    )
