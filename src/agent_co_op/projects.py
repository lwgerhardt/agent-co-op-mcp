"""Project manifests, role-prompt generation, and pickup logic."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .project_store import find_manifest_path, load_project, validate_project_id
from .prompt_builder import build_role_prompt
from .routing import phase_to_role, resolve_routing
from .workspace_paths import HANDOFF_DIRNAME, handoff_dir

_GITIGNORE_MARKER = "# agent-co-op handoff state"
_GITIGNORE_ENTRIES = (
    f"{HANDOFF_DIRNAME}/handoff-state.json",
    f"{HANDOFF_DIRNAME}/handoff.md",
    f"{HANDOFF_DIRNAME}/CURRENT_HANDOFF.md",
    f"{HANDOFF_DIRNAME}/handoff-history/",
    f"{HANDOFF_DIRNAME}/verification-queue.json",
    f"{HANDOFF_DIRNAME}/verification-report.md",
    f"{HANDOFF_DIRNAME}/verification-report.json",
)


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
    validate_project_id(project_id)
    root = handoff_dir(base)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / f"{project_id}.json"
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
    """Bootstrap agent-co-op in a target workspace."""
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
    manifest_path = find_manifest_path(project_id, base=base)
    return {
        "id": project.get("id", project_id),
        "name": project.get("name", project_id),
        "description": project.get("description", ""),
        "repository": project.get("repository", ""),
        "roles": sorted(roles.keys()) if isinstance(roles, dict) else [],
        "manifest_path": str(manifest_path) if manifest_path else "",
    }


def role_prompt(
    project_id: str,
    role: str,
    phase: str | None = None,
    base: Path | None = None,
) -> str:
    """Build and return a paste-ready role-prompt string."""
    from .handoff import read_state

    project = load_project(project_id, base=base)
    routing = resolve_routing(
        role, phase=phase, project_id=project_id, base=base
    )
    state = read_state(base)
    return build_role_prompt(
        project_id=project_id,
        role=role,
        phase=phase,
        project=project,
        routing=routing,
        state=state,
    )


def pickup(project_id: str | None = None, base: Path | None = None) -> str:
    """Return a paste-ready pickup prompt derived from current handoff state."""
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
