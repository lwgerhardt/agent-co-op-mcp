# agent-co-op-mcp

Cross-IDE agent handoff — pickup prompts, role routing, work modes, and a local Python MCP server for Cursor, Claude Code, and VS Code Copilot.

## Problem

Solo developers using multiple AI coding agents (Cursor, Claude Code, VS Code Copilot) lose context every time they switch tools or hit a session limit. There is no shared state about what was decided, what phase the work is in, or what comes next.

**agent-co-op** solves this by writing a small **handoff file** (`.agent-co-op/CURRENT_HANDOFF.md`) that any IDE or agent can paste as a prompt to resume work immediately — no re-planning required.

---

## Quick start

```bash
pip install -e .

# Bootstrap agent-co-op in your project directory
agent-co-op init my-saas --name "My SaaS App"

# Publish a handoff state
agent-co-op handoff publish \
  --objective "Add JWT authentication" \
  --phase implement \
  --project my-saas \
  --next-steps "Write unit tests" "Deploy to staging"

# Generate a paste-ready pickup prompt
agent-co-op pickup
```

`init` creates `.agent-co-op/<project-id>.json` and appends handoff-state entries to `.gitignore` (use `--no-gitignore` to skip). It auto-detects `git remote get-url origin` for the manifest repository field when available.

---

## CLI reference

```bash
# Bootstrap .agent-co-op in the current directory
agent-co-op init <project-id> [--name NAME] [--description TEXT] [--repository URL] [--no-gitignore]

# Generate pickup prompt from current handoff state
agent-co-op pickup [--project ID] [--list]

# Generate a role-prompt for a specific agent
agent-co-op role-prompt <project-id> --role <role> [--phase plan|implement|verify|resume]

# Show routing info for a project
agent-co-op routing show <project-id> [--phase plan|implement|verify|resume]

# Publish, inspect, or clear handoff state
agent-co-op handoff publish --objective "..." --phase implement --project <id> [--next-steps STEP ...]
agent-co-op handoff status [--json]
agent-co-op handoff history [--json] [--limit N] [--id ENTRY_ID]
agent-co-op handoff clear

# Manage project manifests
agent-co-op project init <project-id> [--name NAME] [--description TEXT] [--repository URL]
agent-co-op project show <project-id>
agent-co-op project validate <project-id> [--json]
agent-co-op project validate --file PATH [--expected-id ID] [--json]
```

**Roles:** `scaffold`, `planner`, `verifier`, `efficiency`, `resume`

**Phases:** `plan`, `implement`, `verify`, `resume`

Use `init` for first-time setup in a repo. Use `project init` when you only need the manifest file without gitignore changes.

---

## Project manifests

Each project can have a manifest at `.agent-co-op/<project-id>.json` (or `.agent-co-op/project.json` as a fallback). Manifests are merged into routing and pickup prompts:

| Field | Purpose |
|-------|---------|
| `id`, `name`, `description`, `repository` | Shown in pickup/role prompts |
| `roles.<role>.notes` | Role-specific guidance in prompts |
| `roles.<role>.agent` | Override default agent hint |
| `roles.<role>.model_tier` | Override default model tier |
| `roles.<role>.work_mode` | Override work mode for that role |

See `examples/project.example.json` and `src/agent_co_op/project-manifest.schema.json` for the schema.

Validate a manifest before publishing handoffs:

```bash
agent-co-op project validate my-saas
agent-co-op project validate --file examples/project.example.json --expected-id my-saas
```

---

## MCP server setup

The MCP server (`agent-co-op-mcp`) exposes CLI operations over stdio so any IDE with MCP support can call them without shell copy-paste.

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
| `handoff_status` | JSON snapshot of current handoff state |
| `handoff_history` | JSON list of archived handoff states |
| `project_init` | Create project manifest and optional gitignore entries |
| `project_validate` | Validate a project manifest and return a JSON report |
| `project_show` | Show project manifest summary |
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

| File | Purpose | Git |
|------|---------|-----|
| `<project-id>.json` | Project manifest with role notes and overrides | Commit |
| `handoff-state.json` | Machine-readable state (phase, objective, next_steps) | Ignore (via `init`) |
| `handoff.md` | Human-readable summary | Ignore (via `init`) |
| `CURRENT_HANDOFF.md` | Published pickup file — paste into any IDE | Ignore (via `init`) |
| `handoff-history/` | Archived prior handoff states (JSON + markdown) | Ignore (via `init`) |

---

## Example workflow

```bash
# 0. First-time setup in your repo
agent-co-op init my-saas --name "My SaaS App"

# 1. Start planning
agent-co-op handoff publish \
  --objective "Design the JWT auth system" \
  --phase plan \
  --project my-saas

# 2. Switch to Claude Code — paste the pickup prompt
agent-co-op pickup
# → Role: planner | Work mode: think | Project: My SaaS App | ...

# 3. Planning done — hand off to implementation
agent-co-op handoff publish \
  --objective "Implement JWT auth" \
  --phase implement \
  --project my-saas \
  --next-steps "Write middleware" "Write tests" "Update docs"

# 4. Open Cursor — paste the pickup prompt
agent-co-op pickup
# → Role: verifier | Work mode: background | Next steps: ...

# 5. Check state without generating a full prompt
agent-co-op handoff status

# 5b. Review prior handoffs after republishing
agent-co-op handoff history
agent-co-op handoff history --limit 3 --json

# 6. Implementation done — verify
agent-co-op handoff publish \
  --objective "Verify JWT auth end-to-end" \
  --phase verify \
  --project my-saas

# 7. All done — clear
agent-co-op handoff clear
```

---

## Repository layout

```
.github/workflows/ci.yml   # pytest + ruff on Python 3.10–3.12
src/agent_co_op/
  __init__.py
  routing.py          # roles, work modes, phase→role, resolve routing
  handoff.py          # capture/publish/clear handoff markdown + JSON
  projects.py         # manifests, init workspace, role-prompt, pickup
  manifest.py         # JSON Schema validation for project manifests
  project-manifest.schema.json
  defaults.json       # routing + work_modes config
  cli.py              # CLI entry point (agent-co-op)
  mcp_server.py       # stdio MCP server (agent-co-op-mcp)
tests/
  test_routing.py
  test_handoff.py
  test_handoff_history.py
  test_handoff_status.py
  test_pickup.py
  test_projects.py
  test_manifest.py
  test_cli.py
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
ruff check src/ tests/
```

CI runs on every push and pull request to `main` (see `.github/workflows/ci.yml`).

---

## License

MIT — see [LICENSE](LICENSE).
