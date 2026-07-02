"""CLI entry point for agent-co-op."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import handoff, projects
from .routing import VALID_PHASES, VALID_ROLES, phase_to_role, resolve_routing


def cmd_pickup(args: argparse.Namespace) -> int:
    if args.list:
        state = handoff.read_state()
        if state is None:
            print("No handoff state found.", file=sys.stderr)
            return 1
        print(json.dumps(state, indent=2))
        return 0
    try:
        result = projects.pickup(project_id=args.project or None)
        print(result)
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_role_prompt(args: argparse.Namespace) -> int:
    try:
        result = projects.role_prompt(args.project_id, args.role, phase=args.phase)
        print(result)
        return 0
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_routing_show(args: argparse.Namespace) -> int:
    try:
        phase: str | None = getattr(args, "phase", None)
        role = phase_to_role(phase) if phase else "planner"
        info = resolve_routing(role, phase=phase, project_id=args.project_id)
        print(json.dumps(info, indent=2))
        return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_handoff_publish(args: argparse.Namespace) -> int:
    steps: list[str] = args.next_steps or []
    try:
        handoff.publish(
            args.objective, args.phase, args.project, next_steps=steps or None
        )
        print(f"Handoff published for {args.project} / {args.phase}.")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_handoff_clear(args: argparse.Namespace) -> int:
    handoff.clear()
    print("Handoff files cleared.")
    return 0


def cmd_handoff_status(args: argparse.Namespace) -> int:
    status = handoff.handoff_status()
    if args.json:
        print(json.dumps(status, indent=2))
        return 0
    if not status["has_state"]:
        print("No handoff state found.")
        return 1
    state = status["state"]
    assert state is not None
    print(f"Project:  {state.get('project_id', '(unknown)')}")
    print(f"Phase:    {state.get('phase', '(unknown)')}")
    print(f"Role:     {state.get('role', '(unknown)')}")
    print(f"Objective: {state.get('objective', '(none)')}")
    next_steps: list[str] = state.get("next_steps", [])
    if next_steps:
        print("Next steps:")
        for step in next_steps:
            print(f"  - {step}")
    return 0


def cmd_project_show(args: argparse.Namespace) -> int:
    try:
        summary = projects.project_summary(args.project_id)
        print(json.dumps(summary, indent=2))
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_project_init(args: argparse.Namespace) -> int:
    try:
        path = projects.init_project(
            args.project_id,
            name=args.name,
            description=args.description or "",
            repository=args.repository or "",
        )
        print(f"Project manifest created at {path}")
        return 0
    except FileExistsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_project_validate(args: argparse.Namespace) -> int:
    from .manifest import validate_manifest_file

    if args.file and args.project_id:
        print("Error: specify either project_id or --file, not both.", file=sys.stderr)
        return 2
    if not args.file and not args.project_id:
        print("Error: project_id or --file is required.", file=sys.stderr)
        return 2

    try:
        if args.file:
            report = validate_manifest_file(
                Path(args.file),
                expected_id=args.expected_id,
            )
        else:
            report = projects.validate_project(args.project_id)
            report["project_id"] = args.project_id
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.file:
        report.setdefault("project_id", report.get("id"))

    if args.json:
        print(json.dumps(report, indent=2))
    elif report["valid"]:
        print(f"Manifest valid: {report['manifest_path']}")
        if report["roles"]:
            print(f"Roles: {', '.join(report['roles'])}")
    else:
        print(f"Manifest invalid: {report['manifest_path']}", file=sys.stderr)
        for error in report["errors"]:
            print(f"  - {error}", file=sys.stderr)
    return 0 if report["valid"] else 1


def cmd_init(args: argparse.Namespace) -> int:
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
        return 0
    except FileExistsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-co-op",
        description=(
            "Cross-IDE agent handoff — pickup prompts, role routing, work modes."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init (workspace bootstrap)
    p_init = sub.add_parser(
        "init",
        help="Bootstrap .agent-co-op in the current project directory.",
    )
    p_init.add_argument("project_id", help="Project ID.")
    p_init.add_argument("--name", help="Human-readable project name.")
    p_init.add_argument("--description", help="Short project description.")
    p_init.add_argument(
        "--repository",
        help="Repository URL (defaults to git remote origin when available).",
    )
    p_init.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Do not append handoff-state entries to .gitignore.",
    )
    p_init.set_defaults(func=cmd_init)

    # pickup
    p_pickup = sub.add_parser(
        "pickup", help="Generate pickup prompt from handoff state."
    )
    p_pickup.add_argument("--project", metavar="ID", help="Project ID override.")
    p_pickup.add_argument(
        "--list",
        action="store_true",
        help="Print current handoff state as JSON instead of the prompt.",
    )
    p_pickup.set_defaults(func=cmd_pickup)

    # role-prompt
    p_rp = sub.add_parser("role-prompt", help="Generate a role-prompt for an agent.")
    p_rp.add_argument("project_id", help="Project ID.")
    p_rp.add_argument(
        "--role", required=True, choices=sorted(VALID_ROLES), help="Role name."
    )
    p_rp.add_argument(
        "--phase", choices=sorted(VALID_PHASES), help="Optional phase override."
    )
    p_rp.set_defaults(func=cmd_role_prompt)

    # routing
    p_routing = sub.add_parser("routing", help="Routing commands.")
    routing_sub = p_routing.add_subparsers(dest="routing_command", required=True)
    p_rs = routing_sub.add_parser("show", help="Show routing info for a project.")
    p_rs.add_argument("project_id", help="Project ID.")
    p_rs.add_argument(
        "--phase", choices=sorted(VALID_PHASES), help="Optional phase."
    )
    p_rs.set_defaults(func=cmd_routing_show)

    # handoff
    p_handoff = sub.add_parser("handoff", help="Handoff commands.")
    handoff_sub = p_handoff.add_subparsers(dest="handoff_command", required=True)

    p_hp = handoff_sub.add_parser("publish", help="Publish a handoff state.")
    p_hp.add_argument("--objective", required=True, help="Session objective.")
    p_hp.add_argument(
        "--phase",
        required=True,
        choices=sorted(VALID_PHASES),
        help="Current phase.",
    )
    p_hp.add_argument("--project", required=True, metavar="ID", help="Project ID.")
    p_hp.add_argument(
        "--next-steps",
        nargs="*",
        metavar="STEP",
        help="One or more next steps.",
    )
    p_hp.set_defaults(func=cmd_handoff_publish)

    p_hc = handoff_sub.add_parser("clear", help="Clear all handoff files.")
    p_hc.set_defaults(func=cmd_handoff_clear)

    p_hs = handoff_sub.add_parser("status", help="Show current handoff state.")
    p_hs.add_argument(
        "--json",
        action="store_true",
        help="Print status as JSON instead of a human summary.",
    )
    p_hs.set_defaults(func=cmd_handoff_status)

    # project
    p_project = sub.add_parser("project", help="Project manifest commands.")
    project_sub = p_project.add_subparsers(dest="project_command", required=True)

    p_ps = project_sub.add_parser("show", help="Show a project manifest summary.")
    p_ps.add_argument("project_id", help="Project ID.")
    p_ps.set_defaults(func=cmd_project_show)

    p_pi = project_sub.add_parser("init", help="Create a starter project manifest.")
    p_pi.add_argument("project_id", help="Project ID.")
    p_pi.add_argument("--name", help="Human-readable project name.")
    p_pi.add_argument("--description", help="Short project description.")
    p_pi.add_argument("--repository", help="Repository URL.")
    p_pi.set_defaults(func=cmd_project_init)

    p_pv = project_sub.add_parser("validate", help="Validate a project manifest.")
    p_pv.add_argument(
        "project_id",
        nargs="?",
        help="Project ID to validate under .agent-co-op/.",
    )
    p_pv.add_argument(
        "--file",
        metavar="PATH",
        help="Validate a manifest JSON file directly.",
    )
    p_pv.add_argument(
        "--expected-id",
        metavar="ID",
        help="Expected manifest id when using --file.",
    )
    p_pv.add_argument(
        "--json",
        action="store_true",
        help="Print the validation report as JSON.",
    )
    p_pv.set_defaults(func=cmd_project_validate)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
