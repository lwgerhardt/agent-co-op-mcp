"""Capture, publish, and clear handoff state files in .agent-co-op/."""

from __future__ import annotations

from ..workspace_paths import handoff_dir
from .core import HandoffUpdateError, handoff_status, publish, update
from .history import (
    handoff_history,
    list_history,
    read_history_entry,
    restore,
    safe_history_stem,
)
from .io import clear, read_current_handoff, read_state

# Backward-compatible alias used in tests.
_handoff_dir = handoff_dir
_safe_history_stem = safe_history_stem

__all__ = [
    "HandoffUpdateError",
    "_handoff_dir",
    "_safe_history_stem",
    "clear",
    "handoff_history",
    "handoff_status",
    "list_history",
    "publish",
    "read_current_handoff",
    "read_history_entry",
    "read_state",
    "restore",
    "update",
]
