"""CLI command handlers for agent-co-op.

Each ``cmd_*`` function maps an argparse namespace to a core module call and
returns an exit code (see ``agent_co_op.cli`` for ``EXIT_*`` constants).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .. import handoff, projects, verification
from ..routing import phase_to_role, resolve_routing

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def cmd_pickup(args: argparse.Namespace) -> int:
    """Print pickup prompt or JSON state when ``--list`` is set."""
    if args.list:
        state = handoff.read_state()
        if state is None:
            print("No handoff state found.", file=sys.stderr)
            return EXIT_USAGE
        print(json.dumps(state, indent=2))
        return EXIT_SUCCESS
    try:
        result = projects.pickup(project_id=args.project or None)
        print(result)
        return EXIT_SUCCESS
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE


def cmd_role_prompt(args: argparse.Namespace) -> int:
    """Print a paste-ready role prompt for the given project and role."""
    try:
        result = projects.role_prompt(args.project_id, args.role, phase=args.phase)
        print(result)
        return EXIT_SUCCESS
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE


def cmd_routing_show(args: argparse.Namespace) -> int:
    """Print resolved routing JSON for a project and optional phase."""
    try:
        phase: str | None = getattr(args, "phase", None)
        role = phase_to_role(phase) if phase else "planner"
        info = resolve_routing(role, phase=phase, project_id=args.project_id)
        print(json.dumps(info, indent=2))
        return EXIT_SUCCESS
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE


def cmd_handoff_publish(args: argparse.Namespace) -> int:
    """Publish a new handoff state from CLI flags."""
    steps: list[str] = args.next_steps or []
    try:
        handoff.publish(
            args.objective,
            args.phase,
            args.project,
            next_steps=steps or None,
            context=args.context,
        )
        print(f"Handoff published for {args.project} / {args.phase}.")
        return EXIT_SUCCESS
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR


def cmd_handoff_update(args: argparse.Namespace) -> int:
    """Patch the current handoff without a full republish."""
    if hasattr(args, "next_steps") and hasattr(args, "append_next_steps"):
        print(
            "Error: specify either --next-steps or --append-next-steps, not both.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    try:
        state = handoff.update(
            objective=args.objective,
            phase=args.phase,
            next_steps=args.next_steps if hasattr(args, "next_steps") else None,
            append_next_steps=(
                args.append_next_steps if hasattr(args, "append_next_steps") else None
            ),
            context=args.context,
            clear_context=args.clear_context,
            clear_next_steps=args.clear_next_steps,
        )
    except handoff.HandoffUpdateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(json.dumps(state, indent=2))
    else:
        print(f"Handoff updated for {state['project_id']} / {state['phase']}.")
    return EXIT_SUCCESS


def cmd_handoff_clear(args: argparse.Namespace) -> int:
    """Remove all handoff files under ``.agent-co-op/``."""
    handoff.clear()
    print("Handoff files cleared.")
    return EXIT_SUCCESS


def cmd_handoff_publish_for_verifier(args: argparse.Namespace) -> int:
    """Publish implement-phase handoff and write the verification queue."""
    try:
        queue = verification.publish_for_verifier(
            args.objective,
            args.project,
            profile_id=args.profile,
            next_steps=args.next_steps or None,
            context=args.context,
        )
    except (FileNotFoundError, verification.VerificationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(
        f"Handoff published for verifier: {args.project} / implement "
        f"(profile {queue['profile_id']})."
    )
    print(f"Verification queue: {verification.queue_path()}")
    return EXIT_SUCCESS


def cmd_handoff_status(args: argparse.Namespace) -> int:
    """Show current handoff status as text or JSON."""
    status = handoff.handoff_status()
    if args.json:
        print(json.dumps(status, indent=2))
        return EXIT_SUCCESS
    if not status["has_state"]:
        print("No handoff state found.")
        return EXIT_USAGE
    state = status["state"]
    assert state is not None
    print(f"Project:  {state.get('project_id', '(unknown)')}")
    print(f"Phase:    {state.get('phase', '(unknown)')}")
    print(f"Role:     {state.get('role', '(unknown)')}")
    print(f"Objective: {state.get('objective', '(none)')}")
    handoff_context = state.get("context")
    if isinstance(handoff_context, str) and handoff_context.strip():
        print(f"Context: {handoff_context.strip()}")
    next_steps: list[str] = state.get("next_steps", [])
    if next_steps:
        print("Next steps:")
        for step in next_steps:
            print(f"  - {step}")
    if status.get("verification_warning"):
        print(f"Warning: {status['verification_warning']}")
    return EXIT_SUCCESS


def cmd_verify_run(args: argparse.Namespace) -> int:
    """Run the verification queue and print pass/fail summary."""
    if bool(args.profile) ^ bool(args.project):
        print(
            "Error: --profile and --project must be used together.",
            file=sys.stderr,
        )
        return EXIT_USAGE
    try:
        summary = verification.run_verification(
            profile_id=args.profile,
            project_id=args.project,
            stop_on_failure=not args.continue_on_failure,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except verification.VerificationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Overall: {summary['overall']}")
        for result in summary["results"]:
            print(
                f"  {result['label']}: {result['status']} "
                f"(exit {result.get('exit_code')})"
            )
        manual = summary.get("manual_checks", [])
        if manual:
            print("Manual checks pending:")
            for item in manual:
                print(f"  - {item}")
        print(f"Report: {summary['paths']['report_md']}")

    return EXIT_SUCCESS if summary["overall"] == "PASS" else EXIT_ERROR


def cmd_verify_report(args: argparse.Namespace) -> int:
    """Show metadata for the latest verification report."""
    report = verification.verification_report()
    if args.json:
        print(json.dumps(report, indent=2))
        return EXIT_SUCCESS if report["found"] else EXIT_USAGE
    if not report["found"]:
        print("No verification report found.", file=sys.stderr)
        return EXIT_USAGE
    summary = report["summary"]
    print(f"Overall: {summary.get('overall', '(unknown)')}")
    print(f"Report: {report['paths']['report_md']}")
    return EXIT_SUCCESS


def cmd_handoff_restore(args: argparse.Namespace) -> int:
    """Restore a prior handoff from history as the current state."""
    try:
        state = handoff.restore(args.id)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(json.dumps(state, indent=2))
    else:
        print(
            f"Handoff restored from {args.id} "
            f"for {state['project_id']} / {state['phase']}."
        )
    return EXIT_SUCCESS


def _print_history_entry(entry: dict[str, object]) -> None:
    state = entry["state"]
    assert isinstance(state, dict)
    print(f"ID:        {entry['id']}")
    print(f"Project:   {state.get('project_id', '(unknown)')}")
    print(f"Phase:     {state.get('phase', '(unknown)')}")
    print(f"Role:      {state.get('role', '(unknown)')}")
    print(f"Published: {state.get('published_at', '(unknown)')}")
    print(f"Objective: {state.get('objective', '(none)')}")
    next_steps: list[str] = state.get("next_steps", [])
    if next_steps:
        print("Next steps:")
        for step in next_steps:
            print(f"  - {step}")


def _print_history_list(history: dict[str, object]) -> None:
    entries = history["entries"]
    assert isinstance(entries, list)
    for entry in entries:
        assert isinstance(entry, dict)
        published_at = entry.get("published_at", "(unknown)")
        project_id = entry.get("project_id", "(unknown)")
        phase = entry.get("phase", "(unknown)")
        objective = entry.get("objective", "(none)")
        print(
            f"{entry['id']}\t{published_at}\t{project_id}\t{phase}\t{objective}"
        )


def cmd_handoff_history(args: argparse.Namespace) -> int:
    """List archived handoff entries or show one entry by id."""
    limit = args.limit if args.limit and args.limit > 0 else None
    if args.id:
        entry = handoff.read_history_entry(args.id)
        if entry is None:
            print(f"No history entry found for {args.id!r}.", file=sys.stderr)
            return EXIT_USAGE
        if args.json:
            print(json.dumps(entry, indent=2))
            return EXIT_SUCCESS
        _print_history_entry(entry)
        return EXIT_SUCCESS

    history = handoff.handoff_history(limit=limit)
    if args.json:
        print(json.dumps(history, indent=2))
        return EXIT_SUCCESS
    if history["count"] == 0:
        print("No handoff history found.")
        return EXIT_USAGE
    _print_history_list(history)
    return EXIT_SUCCESS


def cmd_project_show(args: argparse.Namespace) -> int:
    """Print project manifest summary as JSON."""
    try:
        summary = projects.project_summary(args.project_id)
        print(json.dumps(summary, indent=2))
        return EXIT_SUCCESS
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE


def cmd_project_init(args: argparse.Namespace) -> int:
    """Create a starter project manifest under ``.agent-co-op/``."""
    try:
        path = projects.init_project(
            args.project_id,
            name=args.name,
            description=args.description or "",
            repository=args.repository or "",
        )
        print(f"Project manifest created at {path}")
        return EXIT_SUCCESS
    except FileExistsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR


def _load_validation_report(args: argparse.Namespace) -> dict[str, object]:
    from ..manifest import validate_manifest_file

    if args.file:
        report = validate_manifest_file(
            Path(args.file),
            expected_id=args.expected_id,
        )
        report.setdefault("project_id", report.get("id"))
        return report
    report = projects.validate_project(args.project_id)
    report["project_id"] = args.project_id
    return report


def _print_validation_report(report: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2))
        return
    if report["valid"]:
        print(f"Manifest valid: {report['manifest_path']}")
        if report["roles"]:
            print(f"Roles: {', '.join(report['roles'])}")
        return
    print(f"Manifest invalid: {report['manifest_path']}", file=sys.stderr)
    for error in report["errors"]:
        print(f"  - {error}", file=sys.stderr)


def cmd_project_validate(args: argparse.Namespace) -> int:
    """Validate a project manifest by id or ``--file`` path."""
    if args.file and args.project_id:
        print("Error: specify either project_id or --file, not both.", file=sys.stderr)
        return EXIT_USAGE
    if not args.file and not args.project_id:
        print("Error: project_id or --file is required.", file=sys.stderr)
        return EXIT_USAGE

    try:
        report = _load_validation_report(args)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    _print_validation_report(report, as_json=args.json)
    return EXIT_SUCCESS if report["valid"] else EXIT_ERROR


def cmd_init(args: argparse.Namespace) -> int:
    """Bootstrap ``.agent-co-op/`` in the current workspace."""
    try:
        result = projects.init_workspace(
            args.project_id,
            name=args.name,
            description=args.description or "",
            repository=args.repository,
            update_gitignore=not args.no_gitignore,
        )
        print(f"Initialized agent-co-op for {args.project_id}.")
        print(f"Project manifest: {result['manifest_path']}")
        if result["gitignore_updated"]:
            print("Updated .gitignore with handoff-state entries.")
        print("\nNext steps:")
        for command in result["next_commands"]:
            print(f"  {command}")
        return EXIT_SUCCESS
    except FileExistsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR
