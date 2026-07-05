"""agent-co-op: Cross-IDE agent handoff helpers.

Core modules:
    handoff — publish, update, clear, history, restore under ``.agent-co-op/``
    projects — manifests, workspace init, pickup and role prompts
    routing — roles, phases, work modes (see ``defaults.json``)
    verification — verification queue load, run, and reports
    manifest — project manifest JSON Schema validation
    handoff_context — v1/v2 handoff context parse and render
    git_snapshot — optional git branch/status block in handoff state
    handoff_state — warn-only validation of handoff-state JSON

Surfaces:
    cli — ``agent-co-op`` shell commands
    mcp_server — ``agent-co-op-mcp`` stdio MCP tools and resources
"""

__version__ = "0.1.0"
