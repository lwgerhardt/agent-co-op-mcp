"""Verification queue load, run, and report generation."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import ValidationError

from .project_store import load_project
from .workspace_paths import handoff_dir

QUEUE_FILENAME = "verification-queue.json"
REPORT_MD_FILENAME = "verification-report.md"
REPORT_JSON_FILENAME = "verification-report.json"
SCHEMA_PATH = Path(__file__).parent / "verification-queue.schema.json"


class VerificationError(ValueError):
    """Raised when verification input or execution fails."""


def _load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _format_validation_error(error: ValidationError) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    location = f" at {path}" if path else ""
    return f"{error.message}{location}"


def validate_queue_data(queue: Any) -> dict[str, Any]:
    """Validate queue JSON and return a report dict."""
    errors: list[str] = []
    if not isinstance(queue, dict):
        return {"valid": False, "errors": ["Queue must be a JSON object."]}

    validator = jsonschema.Draft202012Validator(_load_schema())
    for error in sorted(validator.iter_errors(queue), key=lambda e: e.path):
        errors.append(_format_validation_error(error))
    return {"valid": len(errors) == 0, "errors": errors}


def queue_path(base: Path | None = None) -> Path:
    return handoff_dir(base) / QUEUE_FILENAME


def report_md_path(base: Path | None = None) -> Path:
    return handoff_dir(base) / REPORT_MD_FILENAME


def report_json_path(base: Path | None = None) -> Path:
    return handoff_dir(base) / REPORT_JSON_FILENAME


def load_queue(base: Path | None = None) -> dict[str, Any] | None:
    path = queue_path(base)
    if not path.exists():
        return None
    queue = json.loads(path.read_text(encoding="utf-8"))
    report = validate_queue_data(queue)
    if not report["valid"]:
        raise VerificationError(
            "Invalid verification queue: " + "; ".join(report["errors"])
        )
    return queue


def write_queue(queue: dict[str, Any], base: Path | None = None) -> Path:
    report = validate_queue_data(queue)
    if not report["valid"]:
        raise VerificationError(
            "Invalid verification queue: " + "; ".join(report["errors"])
        )
    root = handoff_dir(base)
    root.mkdir(parents=True, exist_ok=True)
    path = queue_path(base)
    path.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    return path


def _load_profile(
    project_id: str,
    profile_id: str,
    *,
    base: Path | None = None,
) -> dict[str, Any]:
    project = load_project(project_id, base=base)
    if project is None:
        raise FileNotFoundError(
            f"No project manifest found for {project_id!r}. "
            f"Run 'agent-co-op init {project_id}' first."
        )

    verification = project.get("verification")
    if not isinstance(verification, dict):
        raise VerificationError(
            f"Project {project_id!r} has no verification profiles configured."
        )
    profiles = verification.get("profiles")
    if not isinstance(profiles, dict) or profile_id not in profiles:
        raise VerificationError(
            f"Verification profile {profile_id!r} not found in project manifest."
        )

    profile = profiles[profile_id]
    if not isinstance(profile, dict):
        raise VerificationError(f"Profile {profile_id!r} is invalid.")
    return profile


def _assemble_queue(
    project_id: str,
    profile_id: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    queue: dict[str, Any] = {
        "version": "1.0",
        "profile_id": profile_id,
        "project_id": project_id,
        "commands": profile.get("commands", []),
    }
    expected_branch = profile.get("expected_branch")
    if isinstance(expected_branch, str) and expected_branch:
        queue["expected_branch"] = expected_branch
    manual_checks = profile.get("manual_checks")
    if isinstance(manual_checks, list) and manual_checks:
        queue["manual_checks"] = manual_checks
    return queue


def _validate_queue_or_raise(queue: dict[str, Any], *, prefix: str) -> None:
    report = validate_queue_data(queue)
    if not report["valid"]:
        raise VerificationError(prefix + "; ".join(report["errors"]))


def queue_from_profile(
    project_id: str,
    profile_id: str = "default",
    *,
    base: Path | None = None,
) -> dict[str, Any]:
    """Build a verification queue from a project manifest profile."""
    profile = _load_profile(project_id, profile_id, base=base)
    queue = _assemble_queue(project_id, profile_id, profile)
    _validate_queue_or_raise(queue, prefix="Profile produced invalid queue: ")
    return queue


def publish_for_verifier(
    objective: str,
    project_id: str,
    *,
    profile_id: str = "default",
    next_steps: list[str] | None = None,
    context: str | dict[str, Any] | None = None,
    base: Path | None = None,
) -> dict[str, Any]:
    """Publish implement-phase handoff and write verification queue."""
    from .handoff import publish

    queue = queue_from_profile(project_id, profile_id, base=base)
    publish(
        objective,
        "implement",
        project_id,
        next_steps=next_steps,
        context=context,
        base=base,
    )
    write_queue(queue, base=base)
    return queue


def _run_command(
    command: str,
    *,
    cwd: Path,
    timeout: int | None,
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "FAIL",
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "error": f"Timed out after {timeout}s",
        }
    except OSError as exc:
        return {
            "status": "FAIL",
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "error": str(exc),
        }

    status = "PASS" if result.returncode == 0 else "FAIL"
    return {
        "status": status,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _resolve_run_queue(
    *,
    profile_id: str | None,
    project_id: str | None,
    base: Path | None,
) -> dict[str, Any]:
    if profile_id and project_id:
        queue = queue_from_profile(project_id, profile_id, base=base)
        write_queue(queue, base=base)
        return queue
    queue = load_queue(base)
    if queue is None:
        raise FileNotFoundError(
            "No verification queue found. Run "
            "'agent-co-op handoff publish-for-verifier' or create "
            ".agent-co-op/verification-queue.json first."
        )
    return queue


def _parse_queue_command(cmd: Any) -> dict[str, Any] | None:
    if not isinstance(cmd, dict):
        return None
    cmd_id = str(cmd.get("id", "unknown"))
    timeout_raw = cmd.get("timeout")
    return {
        "id": cmd_id,
        "label": str(cmd.get("label", cmd_id)),
        "command": str(cmd.get("command", "")),
        "timeout": timeout_raw if isinstance(timeout_raw, int) else None,
    }


def _execute_queue_commands(
    queue: dict[str, Any],
    *,
    cwd: Path,
    stop_on_failure: bool,
) -> tuple[str, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    overall = "PASS"
    for cmd in queue.get("commands", []):
        parsed = _parse_queue_command(cmd)
        if parsed is None:
            continue
        outcome = _run_command(
            parsed["command"],
            cwd=cwd,
            timeout=parsed["timeout"],
        )
        results.append(
            {
                "id": parsed["id"],
                "label": parsed["label"],
                "command": parsed["command"],
                **outcome,
            }
        )
        if outcome["status"] == "FAIL" and overall == "PASS":
            overall = "FAIL"
            if stop_on_failure:
                break
    return overall, results


def _build_verification_summary(
    queue: dict[str, Any],
    *,
    overall: str,
    results: list[dict[str, Any]],
    started_at: str,
    finished_at: str,
    base: Path | None,
) -> dict[str, Any]:
    manual_checks = queue.get("manual_checks", [])
    return {
        "overall": overall,
        "profile_id": queue.get("profile_id"),
        "project_id": queue.get("project_id"),
        "started_at": started_at,
        "finished_at": finished_at,
        "results": results,
        "manual_checks": manual_checks if isinstance(manual_checks, list) else [],
        "paths": {
            "queue": str(queue_path(base)),
            "report_md": str(report_md_path(base)),
            "report_json": str(report_json_path(base)),
        },
    }


def run_verification(
    *,
    profile_id: str | None = None,
    project_id: str | None = None,
    stop_on_failure: bool = True,
    base: Path | None = None,
) -> dict[str, Any]:
    """Execute verification queue commands and write reports."""
    root = base or Path.cwd()
    queue = _resolve_run_queue(
        profile_id=profile_id,
        project_id=project_id,
        base=base,
    )
    started_at = datetime.now(timezone.utc).isoformat()
    overall, results = _execute_queue_commands(
        queue,
        cwd=root,
        stop_on_failure=stop_on_failure,
    )
    finished_at = datetime.now(timezone.utc).isoformat()
    summary = _build_verification_summary(
        queue,
        overall=overall,
        results=results,
        started_at=started_at,
        finished_at=finished_at,
        base=base,
    )
    _write_reports(summary, base=base)
    return summary


def _write_reports(summary: dict[str, Any], base: Path | None = None) -> None:
    root = handoff_dir(base)
    root.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Verification report",
        "",
        f"**Overall:** {summary['overall']}",
        f"**Profile:** {summary.get('profile_id', '(unknown)')}",
        f"**Project:** {summary.get('project_id', '(unknown)')}",
        "",
        "| Step | Status | Exit |",
        "|------|--------|------|",
    ]
    for result in summary.get("results", []):
        exit_code = result.get("exit_code")
        exit_display = "" if exit_code is None else str(exit_code)
        lines.append(
            f"| {result.get('label', result.get('id'))} | "
            f"{result.get('status')} | {exit_display} |"
        )

    manual_checks = summary.get("manual_checks", [])
    if manual_checks:
        lines += ["", "## Manual checks (human review required)"]
        for item in manual_checks:
            lines.append(f"- {item}")

    report_md_path(base).write_text("\n".join(lines) + "\n", encoding="utf-8")
    report_json_path(base).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


def verification_report(base: Path | None = None) -> dict[str, Any]:
    """Return latest verification report summary and paths."""
    json_path = report_json_path(base)
    md_path = report_md_path(base)
    if not json_path.exists():
        return {
            "found": False,
            "paths": {
                "report_md": str(md_path),
                "report_json": str(json_path),
                "queue": str(queue_path(base)),
            },
        }

    summary = json.loads(json_path.read_text(encoding="utf-8"))
    return {
        "found": True,
        "summary": summary,
        "paths": summary.get(
            "paths",
            {
                "report_md": str(md_path),
                "report_json": str(json_path),
                "queue": str(queue_path(base)),
            },
        ),
    }


def queue_exists(base: Path | None = None) -> bool:
    return queue_path(base).exists()
