"""Read and write handoff state files."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ..workspace_paths import handoff_dir
from .render import render_handoff_md


def read_state(base: Path | None = None) -> dict[str, Any] | None:
    """Return parsed handoff-state.json, or None if the file is missing."""
    path = handoff_dir(base) / "handoff-state.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Corrupted handoff state at {path}: {exc}. "
            "Run 'agent-co-op handoff clear' to reset."
        ) from exc


def read_current_handoff(base: Path | None = None) -> str | None:
    """Return the contents of CURRENT_HANDOFF.md, or None if missing."""
    path = handoff_dir(base) / "CURRENT_HANDOFF.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def clear(base: Path | None = None) -> None:
    """Remove handoff and verification artifact files from .agent-co-op/."""
    from ..verification import clear_artifacts

    root = handoff_dir(base)
    for name in ("handoff-state.json", "handoff.md", "CURRENT_HANDOFF.md"):
        path = root / name
        if path.exists():
            path.unlink()
    clear_artifacts(base)


def write_handoff_files(state: dict[str, Any], base: Path | None = None) -> None:
    """Write handoff JSON and markdown via temp files, then atomic replace."""
    from ..routing import resolve_routing

    routing = resolve_routing(
        state["role"],
        phase=state["phase"],
        project_id=state["project_id"],
        base=base,
    )
    root = handoff_dir(base)
    root.mkdir(parents=True, exist_ok=True)
    summary_md = render_handoff_md(state, routing, base=base)

    tmp_state = ""
    tmp_handoff_md = ""
    tmp_current_md = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=root,
            prefix=".tmp-",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            json.dump(state, tmp, indent=2)
            tmp_state = tmp.name

        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=root,
            prefix=".tmp-",
            suffix=".md",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(summary_md)
            tmp_handoff_md = tmp.name

        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=root,
            prefix=".tmp-",
            suffix=".md",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(summary_md)
            tmp_current_md = tmp.name

        os.replace(tmp_state, root / "handoff-state.json")
        os.replace(tmp_handoff_md, root / "handoff.md")
        os.replace(tmp_current_md, root / "CURRENT_HANDOFF.md")
    except Exception:
        for tmp_path in (tmp_state, tmp_handoff_md, tmp_current_md):
            if tmp_path:
                try:
                    Path(tmp_path).unlink()
                except OSError:
                    pass
        raise
