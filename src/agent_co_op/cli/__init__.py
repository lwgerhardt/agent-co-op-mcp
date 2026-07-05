"""CLI entry point for agent-co-op.

Exit codes:
    0 — success
    1 — runtime or verification failure
    2 — invalid input or missing handoff/queue

Subcommands delegate to core modules in ``handoff``, ``projects``, ``routing``,
and ``verification``. See ``cli.commands`` for handler implementations and
``cli.parser`` for argparse wiring.
"""

from __future__ import annotations

import sys

from .commands import (
    EXIT_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE,
    cmd_handoff_history,
    cmd_handoff_restore,
    cmd_handoff_status,
    cmd_handoff_update,
    cmd_init,
    cmd_project_init,
    cmd_project_validate,
)
from .parser import build_parser

__all__ = [
    "EXIT_ERROR",
    "EXIT_SUCCESS",
    "EXIT_USAGE",
    "build_parser",
    "cmd_handoff_history",
    "cmd_handoff_restore",
    "cmd_handoff_status",
    "cmd_handoff_update",
    "cmd_init",
    "cmd_project_init",
    "cmd_project_validate",
    "main",
]


def main() -> None:
    """Parse argv and dispatch to the selected subcommand handler."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
