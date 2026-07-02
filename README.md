# agent-co-op-mcp

Cross-IDE agent handoff — pickup prompts, role routing, work modes, and a local Python MCP server for Cursor, Claude Code, and VS Code Copilot.

## Problem

Solo developers using multiple AI coding agents (Cursor, Claude Code, VS Code Copilot) lose context every time they switch tools or hit a session limit. There is no shared state about what was decided, what phase the work is in, or what comes next.

**agent-co-op** solves this by writing a small **handoff file** (`.agent-co-op/CURRENT_HANDOFF.md`) that any IDE or agent can paste as a prompt to resume work immediately — no re-planning required.

---

## Quick start

```bash
pip install -e .

# Publish a handoff state from your project directory
agent-co-op handoff publish \
  --objective "Add JWT authentication" \
  --phase implement \
  --project my-saas \
  --next-steps "Write unit tests" "Deploy to staging"

# Generate a paste-ready pickup prompt
agent-co-op pickup
```

---

## CLI reference

```bash
# Generate pickup prompt from current handoff state
agent-co-op pickup [--project ID] [--list]

# Generate a role-prompt for a specific agent
agent-co-op role-prompt <project-id> --role <role> [--phase plan|implement|verify|resume]

# Show routing info for a project
agent-co-op routing show <project-id> [--phase plan|implement|verify|resume]

# Publish a handoff state
agent-co-op handoff publish --objective "..." --phase implement --project <id> [--next-steps STEP ...]

# Clear all handoff files
agent-co-op handoff clear
```

**Roles:** `scaffold`, `planner`, `verifier`, `efficiency`, `resume`

**Phases:** `plan`, `implement`, `verify`, `resume`

---

## MCP server setup

The MCP server (`agent-co-op-mcp`) exposes the same five operations over stdio so any IDE with MCP support can call them without shell copy-paste.

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "agent-co-op": {
      "command": "agent-co-op-mcp",
      "args": []
    }
  }
}
```

### Claude Code

```bash
claude mcp add agent-co-op -- agent-co-op-mcp
```

Or add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agent-co-op": {
      "command": "agent-co-op-mcp",
      "args": []
    }
  }
}
```

### VS Code Copilot

Add to `.vscode/mcp.json` (VS Code 1.99+):

```json
{
  "servers": {
    "agent-co-op": {
      "type": "stdio",
      "command": "agent-co-op-mcp",
      "args": []
    }
  }
}
```

### Available MCP tools

| Tool | Description |
|------|-------------|
| `handoff_pickup` | Paste-ready prompt for the current handoff state |
| `handoff_role_prompt` | Role-prompt for a specific project/role/phase |
| `handoff_publish` | Write new handoff state files |
| `handoff_clear` | Delete all handoff files |
| `routing_show` | Show routing config for a project and phase |

---

## Work modes

Work modes describe **context and tool discipline** — how much context to load and which tools to use — independent of the underlying model.

| Mode | Description | Best for |
|------|-------------|----------|
| `background` | Throughput — run scripts, verify, resume; minimal reads | `verifier`, `efficiency`, `resume` |
| `think` | Token-sensitive — bootstrap before reads; narrow context | `planner` in `plan` phase |
| `longContext` | Scouting/orientation — large docs and path indexes OK | `scaffold` |
| `default` | Capable implementation loop — balanced reads and writes | `planner` (non-plan phases) |

Phase overrides take precedence over the role default:

| Phase | Role | Effective work mode |
|-------|------|---------------------|
| `plan` | `planner` | `think` |
| `implement` | `verifier` | `background` |
| `verify` | `verifier` | `background` |
| `resume` | `resume` | `background` |

---

## Handoff files

Written to `.agent-co-op/` in the **user's project directory** (not in this repo):

| File | Purpose |
|------|---------|
| `handoff-state.json` | Machine-readable state (phase, objective, project_id, next_steps) |
| `handoff.md` | Human-readable summary |
| `CURRENT_HANDOFF.md` | Published pickup file — paste this into any IDE to resume |

---

## Example workflow

```bash
# 1. Start planning
agent-co-op handoff publish \
  --objective "Design the JWT auth system" \
  --phase plan \
  --project my-saas

# 2. Switch to Claude Code — paste the pickup prompt
agent-co-op pickup
# → Role: planner | Work mode: think | ...

# 3. Planning done — hand off to implementation
agent-co-op handoff publish \
  --objective "Implement JWT auth" \
  --phase implement \
  --project my-saas \
  --next-steps "Write middleware" "Write tests" "Update docs"

# 4. Open Cursor — paste the pickup prompt
agent-co-op pickup
# → Role: verifier | Work mode: background | Next steps: ...

# 5. Implementation done — verify
agent-co-op handoff publish \
  --objective "Verify JWT auth end-to-end" \
  --phase verify \
  --project my-saas

# 6. All done — clear
agent-co-op handoff clear
```

---

## Repository layout

```
src/agent_co_op/
  __init__.py
  routing.py          # roles, work modes, phase→role, resolve routing
  handoff.py          # capture/publish/clear handoff markdown + JSON
  projects.py         # project manifests, role-prompt, pickup logic
  defaults.json       # routing + work_modes config
  cli.py              # CLI entry point (agent-co-op)
  mcp_server.py       # stdio MCP server (agent-co-op-mcp)
tests/
  test_routing.py
  test_handoff.py
  test_pickup.py
examples/
  project.example.json
  handoff-state.example.json
  CURRENT_HANDOFF.example.md
```

---

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src/
```

---

## License

MIT — see [LICENSE](LICENSE).
