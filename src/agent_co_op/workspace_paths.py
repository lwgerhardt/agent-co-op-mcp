"""Shared workspace path helpers for .agent-co-op artifacts."""

from __future__ import annotations

from pathlib import Path

HANDOFF_DIRNAME = ".agent-co-op"


def handoff_dir(base: Path | None = None) -> Path:
    """Return the handoff workspace directory under ``base`` (defaults to cwd)."""
    return (base or Path.cwd()) / HANDOFF_DIRNAME
