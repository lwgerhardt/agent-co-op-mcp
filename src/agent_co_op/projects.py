"""Project manifests, role-prompt generation, and pickup logic."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .routing import resolve_routing, phase_to_role

_HANDOFF_DIRNAME = ".agent-co-op"
_SAFE_PROJECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_GITIGNORE_MARKER = "# agent-co-op handoff state"
_GITIGNORE_ENTRIES = (
    f"{_HANDOFF_DIRNAME}/handoff-state.json",
    f"{_HANDOFF_DIRNAME}/handoff.md",
    f"{_HANDOFF_DIRNAME}/CURRENT_HANDOFF.md",
    f"{_HANDOFF_DIRNAME}/handoff-history/",
    f"{_HANDOFF_DIRNAME}/verification-queue.json",
    f"{_HANDOFF_DIRNAME}/verification-report.md",
    f"{_HANDOFF_DIRNAME}/verification-report.json",
)


def _handoff_dir(base: Path | None = None) -> Path:
    return (base or Path.cwd()) / _HANDOFF_DIRNAME


def _validate_project_id(project_id: str) -> None:
    if not _SAFE_PROJECT_ID.fullmatch(project_id):
        raise ValueError(
            f"Invalid project id {project_id!r}. "
            "Use letters, numbers, dots, underscores, or hyphens; "
            "must start with a letter or number."
        )


def load_project(project_id: str, base: Path | None = None) -> dict[str, Any] | None:
    """Load a project manifest from .agent-co-op/.

    Looks for <project_id>.json then project.json under <base>/.agent-co-op/.
    Returns None if no manifest is found.
    """
    path = find_manifest_path(project_id, base=base)
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def find_manifest_path(project_id: str, base: Path | None = None) -> Path | None:
    """Return the manifest path for a project id, or None if missing."""
    _validate_project_id(project_id)
    d = _handoff_dir(base)
    for candidate in (d / f"{project_id}.json", d / "project.json"):
        if candidate.exists():
            return candidate
    return None


def validate_project(project_id: str, base: Path | None = None) -> dict[str, Any]:
    """Validate the manifest for a project id.

    Raises FileNotFoundError when no manifest exists.
    """
    from .manifest import validate_manifest_file

    path = find_manifest_path(project_id, base=base)
    if path is None:
        raise FileNotFoundError(
            f"No project manifest found for {project_id!r}. "
            f"Run 'agent-co-op init {project_id}' first."
        )
    return validate_manifest_file(path, expected_id=project_id)


def init_project(
    project_id: str,
    name: str | None = None,
    description: str = "",
    repository: str = "",
    base: Path | None = None,
) -> Path:
    """Create a starter project manifest under .agent-co-op/<project_id>.json."""
    _validate_project_id(project_id)
    d = _handoff_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    manifest_path = d / f"{project_id}.json"
    if manifest_path.exists():
        raise FileExistsError(f"Project manifest already exists: {manifest_path}")

    manifest: dict[str, Any] = {
        "id": project_id,
        "name": name or project_id,
        "description": description,
        "repository": repository,
        "roles": {
            "planner": {
                "notes": "Bootstrap from handoff state before broad reads"
            },
            "verifier": {
                "notes": "Run tests and verify acceptance criteria before marking done"
            },
            "scaffold": {
                "notes": "Use the project README and directory layout for orientation"
            },
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _detect_git_repository(base: Path) -> str:
    """Return the origin remote URL when running inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=base,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _ensure_gitignore_entries(base: Path | None = None) -> bool:
    """Append handoff-state gitignore entries when they are not already present."""
    root = base or Path.cwd()
    gitignore_path = root / ".gitignore"
    existing = ""
    if gitignore_path.exists():
        existing = gitignore_path.read_text(encoding="utf-8")
        if _GITIGNORE_MARKER in existing:
            return False
        if all(entry in existing for entry in _GITIGNORE_ENTRIES):
            return False

    block_lines = ["", _GITIGNORE_MARKER, *_GITIGNORE_ENTRIES, ""]
    if existing and not existing.endswith("\n"):
        block_lines.insert(0, "")
    gitignore_path.parent.mkdir(parents=True, exist_ok=True)
    with gitignore_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(block_lines))
    return True


def init_workspace(
    project_id: str,
    name: str | None = None,
    description: str = "",
    repository: str | None = None,
    update_gitignore: bool = True,
    base: Path | None = None,
) -> dict[str, Any]:
    """Bootstrap agent-co-op in a target workspace.

    Creates the project manifest and optionally appends handoff-state entries
    to .gitignore. Returns paths and suggested next commands.
    """
    root = base or Path.cwd()
    repo = repository if repository is not None else _detect_git_repository(root)
    manifest_path = init_project(
        project_id,
        name=name,
        description=description,
        repository=repo,
        base=root,
    )
    gitignore_updated = _ensure_gitignore_entries(root) if update_gitignore else False
    return {
        "project_id": project_id,
        "manifest_path": str(manifest_path),
        "gitignore_updated": gitignore_updated,
        "next_commands": [
            (
                "agent-co-op handoff publish "
                f'--objective "Describe the current goal" --phase plan --project {project_id}'
            ),
            "agent-co-op pickup",
            "agent-co-op handoff status",
        ],
    }


def project_summary(project_id: str, base: Path | None = None) -> dict[str, Any]:
    """Return project manifest metadata and configured roles."""
    project = load_project(project_id, base=base)
    if project is None:
        raise FileNotFoundError(
            f"No project manifest found for {project_id!r}. "
            f"Run 'agent-co-op init {project_id}' first."
        )
    roles = project.get("roles", {})
    return {
        "id": project.get("id", project_id),
        "name": project.get("name", project_id),
        "description": project.get("description", ""),
        "repository": project.get("repository", ""),
        "roles": sorted(roles.keys()) if isinstance(roles, dict) else [],
        "manifest_path": str(_handoff_dir(base) / f"{project_id}.json"),
    }


def _role_notes(project: dict[str, Any] | None, role: str) -> str | None:
    if project is None:
        return None
    roles = project.get("roles", {})
    if not isinstance(roles, dict):
        return None
    role_config = roles.get(role, {})
    if not isinstance(role_config, dict):
        return None
    notes = role_config.get("notes")
    return notes if isinstance(notes, str) and notes.strip() else None


def _normalize_bootstrap_commands(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def _format_read_map_entry(entry: Any) -> str | None:
    if isinstance(entry, str) and entry.strip():
        return entry.strip()
    if isinstance(entry, dict):
        file_path = entry.get("file")
        if not isinstance(file_path, str) or not file_path.strip():
            return None
        parts = [file_path.strip()]
        lines = entry.get("lines")
        if isinstance(lines, str) and lines.strip():
            parts.append(lines.strip())
        why = entry.get("why")
        if isinstance(why, str) and why.strip():
            parts.append(f"— {why.strip()}")
        return " ".join(parts)
    return None


def _append_project_context(
    lines: list[str],
    project: dict[str, Any] | None,
    project_id: str,
) -> None:
    if project is None:
        return
    section: list[str] = []
    name = project.get("name") or project.get("title")
    if isinstance(name, str) and name.strip():
        section.append(f"**Name:** {name}")
    description = project.get("description")
    if isinstance(description, str) and description.strip():
        section.append(f"**Description:** {description}")
    repository = project.get("repository")
    if isinstance(repository, str) and repository.strip():
        section.append(f"**Repository:** {repository}")
    status = project.get("status")
    if isinstance(status, str) and status.strip():
        section.append(f"**Status:** {status}")
    branch = project.get("branch")
    if isinstance(branch, str) and branch.strip():
        section.append(f"**Branch:** {branch}")
    verification_profile = project.get("verification_profile")
    if isinstance(verification_profile, str) and verification_profile.strip():
        section.append(f"**Verification profile:** {verification_profile}")
    if not section:
        section.append(f"**ID:** {project_id}")
    lines += ["", "## Project", *section]


def _append_workflow_context(
    lines: list[str],
    project: dict[str, Any] | None,
    role: str,
) -> None:
    if project is None:
        return

    bootstrap = _normalize_bootstrap_commands(project.get("bootstrap"))
    if bootstrap:
        lines += ["", "## Bootstrap"]
        for command in bootstrap:
            lines.append(f"- `{command}`")

    read_map = project.get("read_map")
    if isinstance(read_map, list):
        entries = [
            formatted
            for item in read_map
            if (formatted := _format_read_map_entry(item)) is not None
        ]
        if entries:
            lines += ["", "## Files to read"]
            for entry in entries:
                lines.append(f"- {entry}")

    if role == "planner":
        planner_notes = project.get("planner_notes")
        if isinstance(planner_notes, str) and planner_notes.strip():
            lines += ["", "## Planner notes", planner_notes.strip()]

    if role == "verifier":
        verifier_notes = project.get("verifier_notes")
        if isinstance(verifier_notes, str) and verifier_notes.strip():
            lines += ["", "## Verifier notes", verifier_notes.strip()]


def role_prompt(
    project_id: str,
    role: str,
    phase: str | None = None,
    base: Path | None = None,
) -> str:
    """Build and return a paste-ready role-prompt string.

    Includes role, agent hint, model tier hint, work mode with discipline bullets,
    and current objective/next-steps from handoff state (if present).

    Raises ValueError for unknown roles or phases.
    """
    from .handoff import read_state

    project = load_project(project_id, base=base)
    routing = resolve_routing(
        role, phase=phase, project_id=project_id, base=base
    )
    state = read_state(base)

    lines: list[str] = [
        f"# Role prompt — {role} / {project_id}",
        "",
        f"**Role:** {role}",
        f"**Agent:** {routing['agent']}",
        f"**Model tier:** {routing['model_tier']}",
        f"**Work mode:** {routing['work_mode']} — {routing['work_mode_description']}",
    ]
    if phase:
        lines.append(f"**Phase:** {phase}")
    _append_project_context(lines, project, project_id)
    _append_workflow_context(lines, project, role)
    role_notes = _role_notes(project, role)
    if role_notes:
        lines += ["", "## Role notes", role_notes]
    lines += ["", "## Context discipline"]
    for bullet in routing["context_discipline"]:
        lines.append(f"- {bullet}")
    lines += ["", "## Tool discipline"]
    for bullet in routing["tool_discipline"]:
        lines.append(f"- {bullet}")

    if state and state.get("project_id") == project_id:
        lines += [
            "",
            "## Current objective",
            state.get("objective", "(none)"),
        ]
        handoff_context = state.get("context")
        if isinstance(handoff_context, str) and handoff_context.strip():
            lines += ["", "## Handoff context", handoff_context.strip()]
        elif isinstance(handoff_context, dict):
            from .handoff_context import format_context_sections, parse_context

            lines += format_context_sections(parse_context(state))
        git_block = state.get("git")
        if isinstance(git_block, dict):
            from .git_snapshot import format_git_section_lines

            lines += format_git_section_lines(git_block)
        next_steps: list[str] = state.get("next_steps", [])
        if next_steps:
            lines += ["", "## Next steps"]
            for step in next_steps:
                lines.append(f"- {step}")
    elif state:
        active_project = state.get("project_id", "unknown")
        lines += [
            "",
            "## Note",
            (
                f"Handoff state exists for a different project ({active_project!r}). "
                "Run 'agent-co-op handoff clear' to reset, or "
                "'agent-co-op handoff history' to inspect."
            ),
        ]

    return "\n".join(lines) + "\n"


def pickup(project_id: str | None = None, base: Path | None = None) -> str:
    """Return a paste-ready pickup prompt derived from current handoff state.

    Raises FileNotFoundError if no handoff state exists; ValueError if state is invalid.
    """
    from .handoff import read_state

    state = read_state(base)
    if state is None:
        raise FileNotFoundError(
            "No handoff state found. Run 'agent-co-op handoff publish' first."
        )

    pid = project_id or state.get("project_id", "unknown")
    phase = state.get("phase", "resume")
    role = state.get("role") or phase_to_role(phase)

    return role_prompt(pid, role, phase=phase, base=base)
