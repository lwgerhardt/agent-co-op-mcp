"""Argparse wiring for the agent-co-op CLI."""

from __future__ import annotations

import argparse

from ..routing import VALID_PHASES, VALID_ROLES
from .commands import (
    cmd_handoff_clear,
    cmd_handoff_history,
    cmd_handoff_publish,
    cmd_handoff_publish_for_verifier,
    cmd_handoff_restore,
    cmd_handoff_status,
    cmd_handoff_update,
    cmd_init,
    cmd_pickup,
    cmd_project_init,
    cmd_project_show,
    cmd_project_validate,
    cmd_role_prompt,
    cmd_routing_show,
    cmd_verify_report,
    cmd_verify_run,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``agent-co-op`` argument parser and subcommands."""
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
    p_hp.add_argument(
        "--context",
        help="Optional decisions, blockers, or background context.",
    )
    p_hp.set_defaults(func=cmd_handoff_publish)

    p_hu = handoff_sub.add_parser(
        "update", help="Patch the current handoff state without republishing."
    )
    p_hu.add_argument("--objective", help="Replace the session objective.")
    p_hu.add_argument(
        "--phase",
        choices=sorted(VALID_PHASES),
        help="Replace the current phase and recompute role/work mode.",
    )
    p_hu.add_argument(
        "--next-steps",
        nargs="*",
        metavar="STEP",
        default=argparse.SUPPRESS,
        help="Replace the full next-steps list.",
    )
    p_hu.add_argument(
        "--append-next-steps",
        nargs="+",
        metavar="STEP",
        default=argparse.SUPPRESS,
        help="Append one or more next steps.",
    )
    p_hu.add_argument(
        "--context",
        help="Replace handoff context (decisions, blockers, notes).",
    )
    p_hu.add_argument(
        "--clear-context",
        action="store_true",
        help="Remove handoff context from the current state.",
    )
    p_hu.add_argument(
        "--clear-next-steps",
        action="store_true",
        help="Remove all next steps from the current state.",
    )
    p_hu.add_argument(
        "--json",
        action="store_true",
        help="Print the updated handoff state as JSON.",
    )
    p_hu.set_defaults(func=cmd_handoff_update)

    p_hc = handoff_sub.add_parser("clear", help="Clear all handoff files.")
    p_hc.set_defaults(func=cmd_handoff_clear)

    p_hs = handoff_sub.add_parser("status", help="Show current handoff state.")
    p_hs.add_argument(
        "--json",
        action="store_true",
        help="Print status as JSON instead of a human summary.",
    )
    p_hs.set_defaults(func=cmd_handoff_status)

    p_hh = handoff_sub.add_parser(
        "history", help="List or show archived handoff states."
    )
    p_hh.add_argument(
        "--json",
        action="store_true",
        help="Print history as JSON instead of a human summary.",
    )
    p_hh.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Return only the N most recent archived entries.",
    )
    p_hh.add_argument(
        "--id",
        metavar="ENTRY_ID",
        help="Show a single archived entry by id.",
    )
    p_hh.set_defaults(func=cmd_handoff_history)

    p_hr = handoff_sub.add_parser(
        "restore", help="Restore a prior handoff state from history."
    )
    p_hr.add_argument(
        "--id",
        required=True,
        metavar="ENTRY_ID",
        dest="id",
        help="Archived entry id from 'agent-co-op handoff history'.",
    )
    p_hr.add_argument(
        "--json",
        action="store_true",
        help="Print the restored handoff state as JSON.",
    )
    p_hr.set_defaults(func=cmd_handoff_restore)

    p_hpf = handoff_sub.add_parser(
        "publish-for-verifier",
        help="Publish implement-phase handoff and write verification queue.",
    )
    p_hpf.add_argument("--objective", required=True, help="Session objective.")
    p_hpf.add_argument("--project", required=True, metavar="ID", help="Project ID.")
    p_hpf.add_argument(
        "--profile",
        default="default",
        help="Verification profile id from project manifest.",
    )
    p_hpf.add_argument(
        "--next-steps",
        nargs="*",
        metavar="STEP",
        help="One or more next steps.",
    )
    p_hpf.add_argument(
        "--context",
        help="Optional decisions, blockers, or background context.",
    )
    p_hpf.set_defaults(func=cmd_handoff_publish_for_verifier)

    # verify
    p_verify = sub.add_parser("verify", help="Verification queue commands.")
    verify_sub = p_verify.add_subparsers(dest="verify_command", required=True)

    p_vr = verify_sub.add_parser("run", help="Run the verification queue.")
    p_vr.add_argument(
        "--profile",
        help="Load queue from project manifest profile instead of queue file.",
    )
    p_vr.add_argument(
        "--project",
        help="Project id (required with --profile).",
    )
    p_vr.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Run all commands even after a failure.",
    )
    p_vr.add_argument(
        "--json",
        action="store_true",
        help="Print verification summary as JSON.",
    )
    p_vr.set_defaults(func=cmd_verify_run)

    p_vrep = verify_sub.add_parser("report", help="Show latest verification report.")
    p_vrep.add_argument(
        "--json",
        action="store_true",
        help="Print report metadata as JSON.",
    )
    p_vrep.set_defaults(func=cmd_verify_report)

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
