"""Handoff filesystem paths and path maps."""

from __future__ import annotations

import re
from pathlib import Path

from ..workspace_paths import handoff_dir

HISTORY_DIRNAME = "handoff-history"
SAFE_ENTRY_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


def history_dir(base: Path | None = None) -> Path:
    return handoff_dir(base) / HISTORY_DIRNAME


def handoff_paths(base: Path | None = None) -> dict[str, str]:
    from ..verification import queue_path, report_json_path, report_md_path

    root = handoff_dir(base)
    return {
        "state_json": str(root / "handoff-state.json"),
        "handoff_md": str(root / "handoff.md"),
        "published_md": str(root / "CURRENT_HANDOFF.md"),
        "history_dir": str(history_dir(base)),
        "verification_queue": str(queue_path(base)),
        "verification_report_md": str(report_md_path(base)),
        "verification_report_json": str(report_json_path(base)),
    }
