"""Archive, list, and restore prior handoff states."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..workspace_paths import handoff_dir
from .io import read_state, write_handoff_files
from .paths import SAFE_ENTRY_ID, history_dir


def safe_history_stem(published_at: str, phase: str) -> str:
    """Build a filename-safe stem from an ISO timestamp and phase."""
    dt = datetime.fromisoformat(published_at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    stamp = dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_phase = re.sub(r"[^a-zA-Z0-9_-]+", "-", phase).strip("-") or "handoff"
    return f"{stamp}_{safe_phase}"


def archive_current_state(base: Path | None = None) -> str | None:
    """Archive the current handoff files before they are overwritten."""
    state = read_state(base)
    if state is None:
        return None

    published_at = state.get("published_at")
    phase = state.get("phase", "handoff")
    if not isinstance(published_at, str) or not published_at:
        published_at = datetime.now(timezone.utc).isoformat()

    archive_dir = history_dir(base)
    archive_dir.mkdir(parents=True, exist_ok=True)

    base_stem = safe_history_stem(published_at, str(phase))
    stem = base_stem
    suffix = 1
    while (archive_dir / f"{stem}.json").exists():
        stem = f"{base_stem}-{suffix}"
        suffix += 1

    (archive_dir / f"{stem}.json").write_text(
        json.dumps(
            {
                **state,
                "archived_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    md_path = handoff_dir(base) / "handoff.md"
    if md_path.exists():
        (archive_dir / f"{stem}.md").write_text(
            md_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    return stem


def list_history(
    base: Path | None = None, limit: int | None = None
) -> list[dict[str, Any]]:
    """Return archived handoff entries, newest first."""
    archive_dir = history_dir(base)
    if not archive_dir.exists():
        return []

    items: list[tuple[str, dict[str, Any]]] = []
    for json_path in archive_dir.glob("*.json"):
        try:
            state = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(
                f"Warning: skipping corrupt history entry {json_path.stem}: {exc}",
                file=sys.stderr,
            )
            continue
        items.append((json_path.stem, state))
    items.sort(
        key=lambda item: item[1].get("archived_at", item[1].get("published_at", "")),
        reverse=True,
    )

    entries: list[dict[str, Any]] = []
    for stem, state in items:
        md_path = archive_dir / f"{stem}.md"
        entries.append(
            {
                "id": stem,
                "published_at": state.get("published_at"),
                "phase": state.get("phase"),
                "project_id": state.get("project_id"),
                "objective": state.get("objective"),
                "role": state.get("role"),
                "has_markdown": md_path.exists(),
            }
        )
        if limit is not None and len(entries) >= limit:
            break
    return entries


def read_history_entry(
    entry_id: str, base: Path | None = None
) -> dict[str, Any] | None:
    """Return a single archived handoff entry by id."""
    if not SAFE_ENTRY_ID.fullmatch(entry_id):
        return None

    archive_dir = history_dir(base)
    json_path = (archive_dir / f"{entry_id}.json").resolve()
    if not json_path.is_relative_to(archive_dir.resolve()):
        return None
    if not json_path.exists():
        return None

    try:
        state = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Corrupted history entry at {json_path}: {exc}."
        ) from exc
    md_path = archive_dir / f"{entry_id}.md"
    markdown = md_path.read_text(encoding="utf-8") if md_path.exists() else None
    return {"id": entry_id, "state": state, "markdown": markdown}


def handoff_history(
    base: Path | None = None, limit: int | None = None
) -> dict[str, Any]:
    """Return archived handoff metadata for CLI/MCP consumers."""
    entries = list_history(base, limit=limit)
    return {"count": len(entries), "entries": entries}


def _validate_archived_required_fields(
    raw_state: dict[str, Any], entry_id: str
) -> None:
    for field in ("phase", "objective", "project_id"):
        value = raw_state.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"History entry {entry_id!r} is missing required field {field!r}."
            )


def _build_restored_state(
    raw_state: dict[str, Any],
    entry_id: str,
    role: str,
    routing: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    next_steps_raw = raw_state.get("next_steps", [])
    next_steps: list[str] = (
        list(next_steps_raw) if isinstance(next_steps_raw, list) else []
    )
    published_at = raw_state.get("published_at")
    if not isinstance(published_at, str) or not published_at:
        published_at = now

    state: dict[str, Any] = {
        "phase": raw_state["phase"],
        "objective": raw_state["objective"],
        "project_id": raw_state["project_id"],
        "role": role,
        "work_mode": routing["work_mode"],
        "next_steps": next_steps,
        "published_at": published_at,
        "updated_at": now,
        "restored_at": now,
        "restored_from_history_id": entry_id,
    }

    context = raw_state.get("context")
    if isinstance(context, str) and context.strip():
        state["context"] = context.strip()
    return state


def restore(entry_id: str, base: Path | None = None) -> dict[str, Any]:
    """Restore a prior handoff state from history as the current handoff."""
    from ..routing import phase_to_role, resolve_routing

    entry = read_history_entry(entry_id, base=base)
    if entry is None:
        raise FileNotFoundError(
            f"No history entry found for {entry_id!r}. "
            "Run 'agent-co-op handoff history' to list ids."
        )

    raw_state = entry["state"]
    _validate_archived_required_fields(raw_state, entry_id)

    archive_current_state(base)

    phase = raw_state["phase"]
    project_id = raw_state["project_id"]
    role = phase_to_role(phase)
    routing = resolve_routing(role, phase=phase, project_id=project_id, base=base)
    now = datetime.now(timezone.utc).isoformat()
    state = _build_restored_state(raw_state, entry_id, role, routing, now)

    from ..git_snapshot import capture_git_snapshot

    git_snapshot = capture_git_snapshot(base)
    if git_snapshot is not None:
        state["git"] = git_snapshot

    write_handoff_files(state, base=base)
    return state
